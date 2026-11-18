import {protect} from '../../lib/access.js';
import {query} from '../../lib/db.js';
import {escape,reply} from '../../lib/replies.js';

export const dynamic = 'force-dynamic';

export async function GET(request) {
  const denied = protect(request);
  if (denied) return denied;
  const code = new URL(request.url).searchParams.get('code') || '';
  const valid = /^[0-9]{6}$/.test(code);
  let result = '';
  let status = 200;
  if (code && !valid) {
    result = '<p role="alert">숫자 6자리 조회 코드를 입력하세요.</p>';
    status = 400;
  } else if (valid) {
    try {
      const {rows} = await query('select numbers from axis_viewer.analysis_tests where code=$1',[code]);
      result = rows.length
        ? '<ol aria-label="테스트 숫자">' + rows[0].numbers.map(n => '<li>' + escape(n) + '</li>').join('') + '</ol>'
        : '<p role="status">해당 코드의 테스트 결과가 없습니다.</p>';
      if (!rows.length) status = 404;
    } catch (error) {
      console.error('Analysis test read:',error.code || 'configuration');
      result = '<p role="alert">테스트 결과를 읽을 수 없습니다.</p>';
      status = 503;
    }
  }
  const html = `<!doctype html><html lang="ko"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>분석 테스트 · axis_migration</title><link rel="stylesheet" href="/graph.css">
    <style>
      body{height:auto;overflow:auto;padding:1.25rem}
      main{max-width:32rem;margin:3rem auto}
      label{display:block;margin-bottom:.5rem}
      input,button{font:inherit;padding:.55rem}
      ol{display:grid;grid-template-columns:repeat(3,1fr);gap:.5rem;padding:0;list-style:none}
      li{background:var(--pane,#222631);border:1px solid var(--line,#404757);padding:1rem;text-align:center}
    </style></head><body><main>
    <a href="/">자료 탐색으로 돌아가기</a><h1>분석 테스트</h1>
    <form action="/analysis-test" method="get">
      <label for="code">MCP에서 받은 조회 코드</label>
      <input id="code" name="code" inputmode="numeric" maxlength="6" pattern="[0-9]{6}"
         autocomplete="off" value="${valid ? code : ''}" required>
      <button type="submit">조회</button>
    </form>${result}</main></body></html>`;
  return reply(html,'text/html; charset=utf-8',{},status);
}
