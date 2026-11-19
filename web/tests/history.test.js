import assert from 'node:assert/strict';
import test from 'node:test';
import pg from 'pg';
import {GET} from '../app/history/route.js';
import {resultCookie} from '../lib/access.js';

test('only operator credentials reveal job codes, file names and extracted text',async t=>{
  process.env.AXIS_VIEWER_PASSWORD='test-password-for-history';
  process.env.DATABASE_URL='postgres://localhost/test';
  const req=(suffix='',headers={})=>new Request('https://example.test/history'+suffix,{headers});
  const headers={authorization:'Basic '+Buffer.from('axis:'+process.env.AXIS_VIEWER_PASSWORD).toString('base64')};
  const doc={name:'<report>.docx',passages:[{location:'문단 1',text:'<원문>'}]};
  const lookup=t.mock.method(pg.Pool.prototype,'query',async sql=>({rows:[sql.includes('j.documents from')
    ? {label:'웹 문서 분석',access_code:'01234567',documents:[doc]}
    : {id:'run-1',files:[doc.name],label:'웹 문서 분석',access_code:'01234567'}]}));
  assert.equal((await GET(req())).status,401);
  assert.equal((await GET(req('?id=run-1&file=0',{cookie:resultCookie(req(),'run-1').split(';')[0]}))).status,401);
  assert.equal(lookup.mock.callCount(),0);
  const list=await GET(req('',headers));
  assert.match(await list.text(),/&lt;report&gt;\.docx/);
  const file=await GET(req('?id=run-1&file=0',headers));
  assert.match(file.headers.get('cache-control'),/no-store/);
  const html=await file.text();
  assert.match(html,/01234567/);
  assert.match(html,/&lt;원문&gt;/);
  assert.equal((await GET(req('?id=run-1&file=9',headers))).status,404);
});
