import {viewerAccess, privateHeaders} from '../../lib/access.js';
import {datasets, dataset, tables, query} from '../../lib/db.js';
import {escape, problem, reply} from '../../lib/replies.js';
import {localGraph, localReview, localViewerEnabled} from '../../lib/local-viewer.js';

export const dynamic = 'force-dynamic';

function selectedFiles(graph, id) {
  if (!id) return null;
  const files = new Set(graph.nodes.filter(n => n.kind === 'file').map(n => n.id));
  if (files.has(id)) return [id];
  return Array.from(new Set(graph.edges.flatMap(edge => {
    if (edge.from === id && files.has(edge.to)) return [edge.to];
    if (edge.to === id && files.has(edge.from)) return [edge.from];
    return [];
  })));
}

function csvField(value) {
  if (value == null) return '"\\N"';
  let text = String(value);
  if (typeof value === 'string' && /^[\t\r\n ]*[=+@-]/.test(text)) text = "'" + text;
  return '"' + text.replaceAll('"','""') + '"';
}

async function sourcePage(params, available) {
  const id = params.get('id') || '';
  const requested = params.get('dataset');
  for (const item of available) {
    if (requested && item.id !== requested) continue;
    const current = await dataset(item.id);
    const node = current.graph.nodes.find(n => n.id === id && n.kind === 'file');
    if (!node) continue;
    const references = (await query(
      `select t.metadata->>'title' as title,r.row_key,r.payload,r.binding
         from axis_viewer.rows r join axis_viewer.tables t
           on t.dataset=r.dataset and t.name=r.table_name
        where r.dataset=$1 and r.file_ids @> array[$2]::text[]
        order by case when r.binding->>'unit_name'=$3 then 0 else 1 end,
                 case when r.table_name in ('source_references','extracted_row') then 0 else 1 end,
                 r.table_name,r.row_key limit 50`,
      [item.id,id,params.get('sheet') || '']
    )).rows;
    const evidence = references.map(row => '<details><summary>' +
      escape(row.title) + ' · ' + escape(row.binding.location || row.row_key) +
      '</summary><dl>' + Object.entries(row.payload).map(([key,value]) =>
        '<dt>' + escape(key) + '</dt><dd>' + escape(value) + '</dd>').join('') + '</dl></details>').join('');
    const location = [params.get('sheet'),params.get('cell'),params.get('page')].filter(Boolean);
    return reply('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width">' +
      '<title>원본 근거 · axis_migration</title><link rel="stylesheet" href="/graph.css">' +
      '<style>body{height:auto;overflow:auto;padding:1rem}main{max-width:65rem;margin:auto}dd{overflow-wrap:anywhere;white-space:pre-wrap}summary{cursor:pointer}details{padding:.5rem}</style>' +
      '<main><a href="/?dataset=' + encodeURIComponent(item.id) + '">자료 탐색으로 돌아가기</a>' +
      '<h1>' + escape(node.label) + '</h1><p>' + escape(location.join(' · ')) + '</p>' +
      '<p>저장된 원본 위치와 추출값입니다. 원본 파일은 로컬 뷰어에서 확인할 수 있습니다.</p>' +
      (evidence || '<p>이 파일에 연결된 추출 행이 없습니다.</p>') + '</main></html>');
  }
  return problem('자료를 찾을 수 없습니다.',404);
}

export async function GET(request) {
  if (localViewerEnabled()) {
    return new URL(request.url).pathname.startsWith('/local-review/')
      ? localReview(request) : localGraph(request);
  }
  const access = viewerAccess(request);
  if (!access) return problem('조회 번호로 자료를 먼저 여세요.',401);
  const {pathname,searchParams:params} = new URL(request.url);
  if (!['/bootstrap.js','/api/rows','/api/detail','/source.html','/csv'].includes(pathname)) {
    return problem('페이지를 찾을 수 없습니다.',404);
  }

  try {
    const available = await datasets(access.dataset);
    if (pathname === '/source.html') return await sourcePage(params,available);
    const fallback = available.find(row => row.id === 'september') || available[0];
    const id = params.get('dataset') || fallback?.id;
    if (access.dataset && id !== access.dataset) return problem('자료 범위를 찾을 수 없습니다.',404);
    const current = await dataset(id);
    if (!current) return problem('자료 범위를 찾을 수 없습니다.',404);
    const metadata = await tables(id);
    if (pathname === '/bootstrap.js') {
      const meta = {dataset:id,datasets:Object.fromEntries(available.map(row => [row.id,row])),
        tables:metadata,catalog:current.catalog,default_table:current.default_table};
      return reply('window.GRAPH_DATA=' + JSON.stringify(current.graph) + ';window.APP_META=' +
        JSON.stringify(meta) + ';', 'text/javascript; charset=utf-8');
    }
    const table = metadata.find(t => t.name === (params.get('table') || current.default_table));
    if (!table) return problem('표를 찾을 수 없습니다.',404);
    if (pathname === '/api/detail') {
      const key = params.get('key') || '';
      if (!/^-?\d{1,19}$/.test(key)) return problem('행 번호를 확인하세요.',400);
      const result = await query(
        'select row_key as key,payload as values,binding from axis_viewer.rows where dataset=$1 and table_name=$2 and row_key::text=$3',
        [id,table.name,key]);
      const row = result.rows[0];
      return row ? Response.json({...row,table:table.name,columns:table.columns},{headers:privateHeaders})
        : problem('행을 찾을 수 없습니다.',404);
    }

    const page = Number(params.get('page') || 0);
    const size = Number(params.get('size') || 50);
    if (!Number.isInteger(page) || page < 0 || page > 1000000 ||
        !Number.isInteger(size) || size < 1 || size > 100) return problem('페이지 범위를 확인하세요.',400);
    const files = selectedFiles(current.graph,params.get('node'));
    const search = (params.get('q') || '').slice(0,200);
    const filters = [id,table.name,files,search];
    const where = `where dataset=$1 and table_name=$2
      and ($3::text[] is null or file_ids && $3::text[])
      and ($4::text='' or strpos(lower(search_text),lower($4)) > 0)`;
    if (pathname === '/csv') {
      const columns = table.columns.map(c => c.name);
      const {rows} = await query('select payload from axis_viewer.rows ' + where + ' order by row_key',filters);
      const stream = new ReadableStream({
        start(controller) {
          const encoder = new TextEncoder();
          controller.enqueue(encoder.encode('\uFEFF' + columns.map(csvField).join(',') + '\r\n'));
          for (const row of rows) controller.enqueue(encoder.encode(columns.map(c => csvField(row.payload[c])).join(',') + '\r\n'));
          controller.close();
        },
      });
      return reply(stream,'text/csv; charset=utf-8',{
        'Content-Disposition':"attachment; filename*=UTF-8''"+encodeURIComponent(table.name+'.csv'),
      });
    }
    const result = await query(`
      with filtered as not materialized (
        select row_key,payload,binding from axis_viewer.rows ${where}
      ), page_rows as (
        select row_key,row_key::text as key,payload as values,binding
          from filtered order by row_key limit $5 offset $6
      )
      select (select count(*) from filtered) as total,
        coalesce((select jsonb_agg(to_jsonb(r) - 'row_key' order by row_key)
          from page_rows r),'[]'::jsonb) as rows`,[...filters,size,page*size]);
    const data = result.rows[0];
    return Response.json({table:table.name,total:Number(data.total),page,size,
      rows:data.rows,columns:table.columns,guide:table.guide},{headers:privateHeaders});
  } catch (error) {
    console.error('Viewer data:', error.code || 'configuration');
    return problem('자료를 읽을 수 없습니다.',503);
  }
}

export async function POST(request) {
  if (new URL(request.url).pathname.startsWith('/local-review/')) return localReview(request);
  return problem('읽기 전용 화면입니다.', 405);
}
