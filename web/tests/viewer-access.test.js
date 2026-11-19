import assert from 'node:assert/strict';
import test from 'node:test';
import pg from 'pg';
import {GET as home} from '../app/route.js';
import {GET as data} from '../app/[...path]/route.js';
import {POST as openResult} from '../app/results/route.js';

test('viewer home is public and an MCP code opens only its own dataset', async t => {
  const password = 'fixture-viewer-password';
  t.mock.method(pg.Pool.prototype, 'query', async (sql, [value]) => {
    if (sql.includes('open_result_code')) {
      return {rows:[value === '01234567' ? {dataset_id:folder, landing_table:'summary'} : {}]};
    }
    if (sql.includes('order by id')) {
      assert.ok(sql.includes("id !~ '^run-[a-f0-9]{32}$'"));
      return {rows:[{id:value ?? 'september'}]};
    }
    assert.equal(value, folder);
    return {rows:sql.includes('axis_viewer.datasets') ? [{graph:{nodes:[]}}] : []};
  });

  const folder = 'run-' + 'a'.repeat(32);
  const other = 'run-' + 'b'.repeat(32);
  const previous = {...process.env};
  t.after(() => {
    for (const key of ['AXIS_LOCAL_GRAPH_URL', 'AXIS_VIEWER_PASSWORD', 'DATABASE_URL']) {
      if (previous[key] === undefined) delete process.env[key];
      else process.env[key] = previous[key];
    }
  });
  delete process.env.AXIS_LOCAL_GRAPH_URL;
  process.env.AXIS_VIEWER_PASSWORD = password;
  process.env.DATABASE_URL = 'postgres://fixture@localhost/fixture';

  const request = (path, init) => new Request('http://localhost' + path, init);
  const lookup = code => openResult(request('/results', {method:'POST', body:new URLSearchParams({code})}));
  const landing = await home(request('/'));
  assert.equal(landing.status, 200);
  assert.match(await landing.text(), /href="\/results"/);

  const basic = {authorization:'Basic ' + Buffer.from('axis:' + password).toString('base64')};
  const invalid = await lookup('99999999');
  assert.equal(invalid.status, 404);
  assert.equal(invalid.headers.has('set-cookie'), false);
  const granted = await lookup('01234567');
  assert.equal(granted.status, 303);
  const headers = {cookie:granted.headers.get('set-cookie').split(';')[0]};
  const viewer = await home(request(granted.headers.get('location'), {headers}));
  assert.equal(viewer.status, 200);
  assert.match(await viewer.text(), new RegExp('bootstrap.js\\?dataset=' + folder));

  for (const path of ['/bootstrap.js', '/api/rows', '/api/detail', '/csv', '/source.html']) {
    assert.equal((await data(request(`${path}?dataset=${folder}`))).status, 401);
    assert.equal((await data(request(`${path}?dataset=${folder}`, {headers:basic}))).status, 404);
    assert.equal((await data(request(`${path}?dataset=${other}`, {headers}))).status, 404);
  }
  const bootstrap = await data(request(`/bootstrap.js?dataset=${folder}`, {headers}));
  assert.equal(bootstrap.status, 200);
  assert.match(await bootstrap.text(), new RegExp(folder));
});
