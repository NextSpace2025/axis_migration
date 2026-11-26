import {spawn} from 'node:child_process';
import {once} from 'node:events';
import {readFileSync} from 'node:fs';
import {createInterface} from 'node:readline';
import {fileURLToPath} from 'node:url';
import pg from 'pg';
import {isResultCode, resultCode} from '../lib/result-code.js';

const args = process.argv.slice(2);
const dryRun = args[0] === '--dry-run';
if (dryRun) args.shift();
const folderRun = args[0] === '--run';
if (folderRun) args.shift();
// --update replaces an earlier upload of the same run (a grown ledger) and keeps its lookup code.
const update = folderRun && args[0] === '--update';
if (update) args.shift();
const [viewer, ...datasets] = args;
const databaseUrl = process.env.AXIS_IMPORT_DATABASE_URL || (folderRun && process.env.DATABASE_URL);
if (!viewer || (folderRun ? datasets.length : !datasets.length) || (!dryRun && !databaseUrl)) {
  console.error('Usage: npm run import -- [--dry-run] <integrated_server.py> <dataset> [<dataset> ...]');
  console.error('For an actual import, set AXIS_IMPORT_DATABASE_URL.');
  console.error('For an approved run: node --env-file=.env scripts/import.mjs --run <run-directory>');
  process.exit(2);
}

const client = dryRun ? null : new pg.Client(folderRun ? hostedConnection(databaseUrl) : {connectionString:databaseUrl});
const counts = new Map();
let batch = [];
let child;
let finished = false;
let folder;
let existingCode;
let unchanged = false;
let primaryCount;
let committed = false;
let disconnected = false;

function hostedConnection(value) {
  const url = new URL(value);
  if (['127.0.0.1','localhost'].includes(url.hostname)) return {connectionString:url.href};
  if (!(url.hostname.endsWith('.supabase.co') || url.hostname.endsWith('.pooler.supabase.com'))) {
    throw new Error('Supabase 접속 주소를 확인하세요.');
  }
  for (const field of ['ssl','sslmode','sslrootcert','sslcert','sslkey']) url.searchParams.delete(field);
  const ca = process.env.DATABASE_CA_PEM || readFileSync(new URL('../lib/supabase-ca.crt',import.meta.url),'utf8');
  return {connectionString:url.href,ssl:{ca,rejectUnauthorized:true},connectionTimeoutMillis:10000};
}

async function publishCode() {
  const saved = await client.query('select count(*) from axis_viewer.rows where dataset=$1',[folder.id]);
  if (Number(saved.rows[0].count) !== counts.get(folder.id)) throw new Error('Uploaded row count mismatch');
  if (existingCode) return existingCode;
  for (let attempt=0;attempt<20;attempt++) {
    const code = resultCode();
    const result = await client.query(`
      update axis_viewer.datasets set access_code=$2 where id=$1 and access_code is null
      and not exists(select 1 from axis_viewer.datasets where access_code=$2) returning access_code`,
    [folder.id,code]);
    if (result.rowCount) return code;
  }
  throw new Error('Unable to allocate a dataset code');
}

async function verifyPage(base, code) {
  const headers = {};
  const get = path => fetch(new URL(path,base),{headers,redirect:'manual',signal:AbortSignal.timeout(20000)});
  const link = '/results?code='+code;
  const response = await get(link);
  const destination = new URL(response.headers.get('location') || '/',base);
  if (response.status !== 303 || destination.origin !== base.origin ||
      destination.pathname !== '/' || destination.searchParams.get('dataset') !== folder.id ||
      destination.searchParams.get('table') !== folder.default_table) {
    throw new Error('Hosted result code did not open the dataset');
  }
  const cookie = response.headers.get('set-cookie')?.split(';',1)[0];
  if (!cookie?.startsWith('axis_dataset_view=')) throw new Error('Hosted viewer session was not issued');
  headers.Cookie = cookie;
  const page = await get(destination);
  if (!page.ok || !(await page.text()).includes('bootstrap.js?dataset='+folder.id)) {
    throw new Error('Hosted viewer did not open the dataset');
  }
  const tableQuery = new URLSearchParams({dataset:folder.id,table:folder.default_table,size:'1'});
  const rows = await get('/api/rows?'+tableQuery);
  if (!rows.ok) throw new Error('Hosted table did not load');
  const data = await rows.json();
  if (data.total !== primaryCount || data.rows.length !== 1) throw new Error('Hosted table row count mismatch');
  const graph = await get('/bootstrap.js?'+new URLSearchParams({dataset:folder.id}));
  if (!graph.ok || !(await graph.text()).includes('window.GRAPH_DATA=')) throw new Error('Hosted graph did not load');
  const file = folder.graph.nodes.find(node => node.kind === 'file');
  if (file) {
    const source = await get('/source.html?'+new URLSearchParams({dataset:folder.id,id:file.id}));
    if (!source.ok) throw new Error('Hosted evidence did not load');
  }
  return {code,viewer_url:new URL(link,base).href,dataset:folder.id};
}

async function flush() {
  if (client && batch.length) {
    await client.query(`insert into axis_viewer.rows
      select * from jsonb_to_recordset($1) as rows (
        dataset text, table_name text, row_key bigint, payload jsonb, binding jsonb,
        file_ids text[], search_text text)`,['[' + batch.join(',') + ']']);
  }
  batch = [];
}

try {
  let base;
  if (folderRun && client) {
    base = new URL(process.env.AXIS_VIEWER_URL);
    const local = ['127.0.0.1','localhost'].includes(base.hostname);
    if ((base.protocol !== 'https:' && !(local && base.protocol === 'http:')) ||
        base.username || base.password || base.pathname !== '/' || base.search || base.hash) {
      throw new Error('AXIS_VIEWER_URL must be configured');
    }
  }
  if (client) {
    await client.connect();
    await client.query('begin');
    await client.query("select pg_advisory_xact_lock(hashtext('axis_viewer import'))");
  }
  child = spawn(process.env.AXIS_PYTHON || 'python',
    ['-X','utf8',fileURLToPath(new URL(folderRun ? './folder_snapshot.py' : './snapshot.py',import.meta.url)),viewer,...datasets],
    {stdio:['ignore','pipe','inherit']});
  const exit = once(child,'close');
  exit.catch(() => {});
  const lines = createInterface({input:child.stdout,crlfDelay:Infinity});
  for await (const line of lines) {
    const {kind,...data} = JSON.parse(line);
    if (kind === 'dataset') {
      counts.set(data.id,0);
      if (folderRun) {
        folder = data;
        if (!client) continue;
        const {rows:[existing]} = await client.query(
          'select access_code,snapshot_sha256 from axis_viewer.datasets where id=$1',[data.id]);
        if (existing) {
          if (!isResultCode(existing.access_code) ||
              (existing.snapshot_sha256 !== data.snapshot_sha256 && !update)) {
            throw new Error('Existing result does not match this verified run');
          }
          existingCode = existing.access_code;
          unchanged = existing.snapshot_sha256 === data.snapshot_sha256;
          if (!unchanged) {
            await client.query('delete from axis_viewer.rows where dataset=$1',[data.id]);
            await client.query('delete from axis_viewer.tables where dataset=$1',[data.id]);
            await client.query(`update axis_viewer.datasets set label=$2,description=$3,default_table=$4,
              catalog=$5,graph=$6,snapshot_sha256=$7 where id=$1`,
            [data.id,data.label,data.description,data.default_table,data.catalog,data.graph,data.snapshot_sha256]);
          }
        } else {
          await client.query(`insert into axis_viewer.datasets
            (id,label,description,default_table,catalog,graph,snapshot_sha256) values ($1,$2,$3,$4,$5,$6,$7)`,
          [data.id,data.label,data.description,data.default_table,data.catalog,data.graph,data.snapshot_sha256]);
        }
      } else if (client) {
        await client.query('delete from axis_viewer.datasets where id=$1',[data.id]);
        await client.query(`insert into axis_viewer.datasets
          (id,label,description,default_table,catalog,graph) values ($1,$2,$3,$4,$5,$6)`,
          [data.id,data.label,data.description,data.default_table,data.catalog,data.graph]);
      }
    } else if (kind === 'table') {
      if (folderRun && data.name === folder.default_table) primaryCount = data.metadata.count;
      if (client && !unchanged) await client.query('insert into axis_viewer.tables values ($1,$2,$3)',
        [data.dataset,data.name,data.metadata]);
    } else if (kind === 'row') {
      counts.set(data.dataset,counts.get(data.dataset)+1);
      if (client && !unchanged) batch.push(line);
      if (batch.length >= 200) await flush();
    } else if (kind === 'complete') {
      finished = true;
    } else {
      throw new Error('Unexpected record type');
    }
  }
  const [code] = await exit;
  if (code !== 0 || !finished) throw new Error('Incomplete SQLite export');
  await flush();
  const accessCode = folderRun && client ? await publishCode() : null;
  if (client) {
    await client.query('commit');
    committed = true;
    await client.end();
    disconnected = true;
  }
  if (accessCode) {
    console.log(JSON.stringify(await verifyPage(base,accessCode)));
  } else {
    for (const [id, count] of counts) console.log(id + ': ' + count + (dryRun ? ' rows verified' : ' rows imported'));
  }
} catch (error) {
  child?.kill();
  if (client && !committed) await client.query('rollback').catch(() => {});
  console.error('Import failed:',error.code || (folderRun ? 'Check database and viewer settings, or retry the run.' : error.message));
  process.exitCode = 1;
} finally {
  if (client && !disconnected) await client.end();
}
