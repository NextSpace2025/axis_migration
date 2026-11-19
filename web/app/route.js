import {entryPage} from '../lib/viewer-shell.js';
import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {privateHeaders, viewerAccess} from '../lib/access.js';
import {reply} from '../lib/replies.js';
import {datasets} from '../lib/db.js';
import {localGraph, localViewerEnabled} from '../lib/local-viewer.js';

export const dynamic = 'force-dynamic';

function viewerHome(message) {
  return reply(entryPage('자료 탐색', `<p>${message}</p><div class="analysis-actions"><a class="text-action" href="/documents">문서 올리고 분석하기</a><a class="text-action" href="/results">조회 번호로 결과 열기</a></div>`));
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
