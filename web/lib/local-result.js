import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {DatabaseSync} from 'node:sqlite';
import {problem} from './replies.js';

const quote = name => '"' + name.replaceAll('"', '""') + '"';
const scalar = value => typeof value === 'bigint'
  ? (Number.isSafeInteger(Number(value)) ? Number(value) : String(value))
  : value instanceof Uint8Array ? Buffer.from(value).toString('hex') : value;
const localHeaders = {'cache-control':'no-store', 'x-content-type-options':'nosniff'};

function select(db, sql) {
  const statement = db.prepare(sql);
  statement.setReadBigInts(true);
  return statement;
}

function fields(db, table) {
  return db.prepare('PRAGMA table_info(' + quote(table) + ')').all();
}

function columns(info, guide = {}) {
  return info.map(field => ({...guide[field.name], name:field.name}));
}

function resultGraph(db, tables) {
  const nodes = tables.map((table, index) => {
    const angle = 2 * Math.PI * index / tables.length;
    return {id:table.name, label:table.title, kind:'table', x:180 * Math.cos(angle), y:180 * Math.sin(angle)};
  });
  const names = new Map(nodes.map(node => [node.id, node.label]));
  const edges = tables.flatMap(({name}) => {
    const keys = db.prepare('PRAGMA foreign_key_list(' + quote(name) + ')').all();
    return keys.filter(key => key.seq === 0 && names.has(key.table)).map(key => {
      const parts = keys.filter(part => part.id === key.id);
      return {id:name + ':' + key.id, from:name, to:key.table, status:'observed',
        label:'외래 키', note:names.get(name) + ' → ' + names.get(key.table),
        evidence:[{quote:parts.map(part => part.from + ' → ' + (part.to || '기본 키')).join(', '),
          source_name:'SQLite 외래 키'}]};
    });
  });
  return {nodes, edges, counts:{tables:nodes.length}};
}

function rowsFor(db, table, params, guide) {
  const info = fields(db, table);
  const keys = info.filter(field => field.pk).sort((a, b) => a.pk - b.pk).map(field => field.name);
  const keyColumns = keys.length ? keys.map(quote) : ['rowid'];
  const columnList = info.map(field => quote(field.name));
  const selectors = keyColumns.concat(columnList).join(', ');
  const from = ' FROM ' + quote(table);
  const order = ' ORDER BY ' + keyColumns.join(', ');
  const query = (params.get('q') || '').slice(0, 200).toLowerCase();
  const where = query ? ' WHERE (' + columnList.map(name =>
    'instr(lower(CAST(' + name + ' AS TEXT)), ?) > 0').join(' OR ') + ')' : '';
  const args = query ? columnList.map(() => query) : [];
  const metadata = columns(info, guide.columns);
  function clean(row) {
    const ids = row.slice(0, keyColumns.length).map(scalar);
    const values = Object.fromEntries(info.map((field, i) => [field.name, scalar(row[i + ids.length])]));
    return {key:JSON.stringify(ids), values, binding:sourceBinding(values, table, ids)};
  }
  function asArrays(sql) {
    const statement = select(db, sql);
    statement.setReturnArrays(true);
    return statement;
  }
  return {
    metadata,
    all: () => asArrays('SELECT ' + columnList.join(', ') + from + where + order).all(...args),
    page() {
      const size = Math.min(100, Math.max(1, Number.parseInt(params.get('size'), 10) || 50));
      const page = Math.min(10_000_000, Math.max(0, Number.parseInt(params.get('page'), 10) || 0));
      const rows = asArrays('SELECT ' + selectors + from + where + order + ' LIMIT ? OFFSET ?')
        .all(...args, size, page * size).map(clean);
      const total = db.prepare('SELECT count(*) AS count' + from + where).get(...args).count;
      return {columns:metadata, rows, total};
    },
    detail(key) {
      let ids;
      try { ids = JSON.parse(key); } catch { return null; }
      if (!Array.isArray(ids) || ids.length !== keyColumns.length ||
          ids.some(id => id !== null && !['string', 'number'].includes(typeof id))) return null;
      const row = asArrays('SELECT ' + selectors + from + ' WHERE ' +
        keyColumns.map(name => name + ' IS ?').join(' AND ') + ' LIMIT 1').get(...ids);
      return row ? {...clean(row), table, columns:metadata} : null;
    },
  };
}

function sourceBinding(values, table) {
  const source = typeof values.source_path === 'string' ? values.source_path
    : table === 'source_files' ? values.path : null;
  const line = values.physical_line;
  return {node_ids:[table], source_row:line, sources:source ? [{
    label:source, location:line != null ? line + '행' : '원본 파일',
  }] : []};
}

function csvValue(value) {
  if (value === null) return '"\\N"';
  const text = String(scalar(value));
  const safe = typeof value === 'string' && /^[\t\r\n ]*[=+@-]/.test(text) ? "'" + text : text;
  return '"' + safe.replaceAll('\\', '\\\\').replaceAll('"', '""') + '"';
}

export async function localResult(run, route, params, datasets) {
  if (route === '/sql') {
    const sql = await readFile(path.join(run.folder, 'export.sql'));
    return new Response(sql, {headers:{...localHeaders, 'content-type':'application/sql; charset=utf-8',
      'content-disposition':'attachment; filename="axis-migration.sql"'}});
  }
  const config = JSON.parse(await readFile(path.join(run.folder, 'viewer.json'), 'utf8'));
  const db = new DatabaseSync(path.join(run.folder, 'data.sqlite'), {readOnly:true, allowExtension:false});
  try {
    db.exec('PRAGMA trusted_schema = OFF');
    const catalog = config.catalog || {};
    const guides = catalog.tables || {};
    const names = db.prepare("SELECT name FROM sqlite_schema WHERE type='table' AND name NOT GLOB 'sqlite_*' ORDER BY name").all()
      .map(row => row.name);
    const defaultTable = names.includes(config.primary_table) ? config.primary_table : names[0];
    if (!defaultTable) return problem('변환된 업무 표가 없습니다.', 404);
    if (route === '/bootstrap.js') {
      const tables = names.map(name => {
        const guide = guides[name] || {};
        return {name, guide, title:guide.title || guide.label || name, group:guide.group || '변환 결과',
          columns:columns(fields(db, name), guide.columns),
          count:db.prepare('SELECT count(*) AS count FROM ' + quote(name)).get().count};
      });
      const dataset = 'review:' + run.id;
      const choice = {label:run.label + ' · 변환 결과', description:'SQLite 검증 완료', default_table:defaultTable};
      const meta = {dataset, localResult:true, tables, catalog, default_table:defaultTable};
      const extra = {...datasets, [dataset]:choice};
      return new Response(`window.GRAPH_DATA=${JSON.stringify(resultGraph(db, tables))};
window.APP_META={...${JSON.stringify(meta)},datasets:{...window.APP_META?.datasets,...${JSON.stringify(extra)}}};`,
        {headers:{...localHeaders, 'content-type':'text/javascript; charset=utf-8'}});
    }
    const table = params.get('table') || defaultTable;
    if (!names.includes(table)) return problem('표를 찾을 수 없습니다.', 404);
    const rows = rowsFor(db, table, params, guides[table] || {});
    if (route === '/api/rows') return Response.json(rows.page(), {headers:localHeaders});
    if (route === '/api/detail') {
      const detail = rows.detail(params.get('key'));
      return detail ? Response.json(detail, {headers:localHeaders}) : problem('행을 찾을 수 없습니다.', 404);
    }
    if (route === '/csv') {
      const csv = [rows.metadata.map(field => csvValue(field.name)), ...rows.all().map(row => row.map(csvValue))]
        .map(row => row.join(',')).join('\r\n');
      return new Response('\uFEFF' + csv + '\r\n', {headers:{...localHeaders, 'content-type':'text/csv; charset=utf-8',
        'content-disposition':'attachment; filename="axis-migration.csv"'}});
    }
    return problem('결과 화면을 찾을 수 없습니다.', 404);
  } finally {
    db.close();
  }
}
