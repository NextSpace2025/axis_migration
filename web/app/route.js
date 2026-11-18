import {readFile} from 'node:fs/promises';
import path from 'node:path';
import {privateHeaders, viewerAccess} from '../lib/access.js';
import {reply} from '../lib/replies.js';
import {datasets} from '../lib/db.js';
import {localGraph, localViewerEnabled} from '../lib/local-viewer.js';

export const dynamic = 'force-dynamic';

export async function GET(request) {
  if (localViewerEnabled()) return localGraph(request, true);
  const access = viewerAccess(request);
  if (!access) return new Response(null,{status:303,headers:{...privateHeaders,Location:'/results'}});
  try {
    const available = await datasets(access.dataset);
    if (!available.length) {
      return reply('<meta charset="utf-8"><p>가져온 자료가 없습니다.</p><a href="/results">조회 번호 입력</a>');
    }
    const requested = new URL(request.url).searchParams.get('dataset');
    if (access.dataset && requested && requested !== access.dataset) {
      return new Response(null,{status:303,headers:{...privateHeaders,Location:'/results'}});
    }
    const selected = available.find(row => row.id === requested)
      || available.find(row => row.id === 'september') || available[0];
    const html = await readFile(path.join(process.cwd(), 'lib', 'viewer.html'), 'utf8');
    return reply(html.replace('__DATASET__', encodeURIComponent(selected.id)));
  } catch (error) {
    console.error('Viewer startup:', error.code || 'configuration');
    return new Response('자료 서버 설정을 확인해 주세요.', {status:503});
  }
}
