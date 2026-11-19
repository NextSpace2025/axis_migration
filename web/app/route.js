import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {privateHeaders, viewerAccess} from '../lib/access.js';
import {reply} from '../lib/replies.js';
import {datasets} from '../lib/db.js';
import {localGraph, localViewerEnabled} from '../lib/local-viewer.js';

export const dynamic = 'force-dynamic';

function viewerHome(message) {
  return reply(`<!doctype html><html lang="ko"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>AXIS 자료 뷰어</title><link rel="stylesheet" href="/graph.css">
    <style>body{height:auto;overflow:auto}main{max-width:32rem;margin:clamp(2rem,9vw,6rem) auto;padding:0 1.25rem}
    p{margin:.75rem 0 1rem}a{display:inline-block;padding:.55rem 0}</style></head>
    <body><main><h1>AXIS 자료 뷰어</h1><p>${message}</p>
    <a href="/documents">문서 올리고 분석하기</a> · <a href="/results">조회 번호로 결과 열기</a></main></body></html>`);
}

export async function GET(request) {
  if (localViewerEnabled()) return localGraph(request, true);
  const access = viewerAccess(request);
  if (!access) return viewerHome('MCP에서 받은 8자리 조회 번호로 작업 결과를 볼 수 있습니다.');
  try {
    const requested = new URL(request.url).searchParams.get('dataset');
    const available = await datasets(access.dataset);
    const selected = available.find(row => row.id === requested);
    if (requested && !selected) {
      return new Response(null,{status:303,headers:{...privateHeaders,Location:'/results'}});
    }
    if (!available.length) {
      return viewerHome('현재 열 수 있는 자료가 없습니다.');
    }
    const current = selected || available.find(row => row.id === 'september') || available[0];
    if (current.default_table === '__web_topics__') {
      return new Response(null,{status:303,headers:{...privateHeaders,Location:'/documents?id='+encodeURIComponent(current.id)}});
    }
    const html = await readFile(path.join(process.cwd(), 'lib', 'viewer.html'), 'utf8');
    return reply(html.replace('__DATASET__', encodeURIComponent(current.id)));
  } catch (error) {
    console.error('Viewer startup:', error.code || 'configuration');
    return new Response('자료 서버 설정을 확인해 주세요.', {status:503});
  }
}
