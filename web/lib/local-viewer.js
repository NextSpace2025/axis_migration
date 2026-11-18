import {readFile, readdir} from 'node:fs/promises';
import path from 'node:path';
import {escape, problem} from './replies.js';
import {isResultCode} from './result-code.js';
import {localResult} from './local-result.js';

const runId = /^\d{8}T\d{6}Z-[a-f0-9]{6}$/;
const legacyPath = /^\/(?:index\.html|bootstrap\.js|source\.html|source\.js|qa\.html|qa\.js|health|api\/(?:rows|detail)|csv|sql|(?:source-meta|sheet|asset|text)\/[SP]\d{3}|preview\/S\d{3}\/\d+)$/;
const legacyAsset = /^(?:graph\.css|integrated\.css|integrated\.js|graph_engine\.js|graph3d\.js|purpose-navigation\.js)$/;
const resultRoutes = new Set(['/bootstrap.js', '/api/rows', '/api/detail', '/csv', '/sql']);
const forwardedHeaders = ['content-type', 'content-disposition', 'content-security-policy',
  'referrer-policy', 'x-content-type-options'];

export function localViewerEnabled() {
  return Boolean(process.env.AXIS_LOCAL_GRAPH_URL);
}

function loopbackURL(value) {
  const url = new URL(value);
  if (url.protocol !== 'http:' || url.hostname !== '127.0.0.1' || !url.port ||
      url.username || url.password || url.hash) {
    throw new Error('Use an explicit 127.0.0.1 HTTP port.');
  }
  return url;
}

function hostedResultURL(value) {
  try {
    const url = new URL(value);
    if (url.protocol === 'https:' && !url.username && !url.password &&
        url.pathname === '/results' && isResultCode(url.searchParams.get('code'))) return url.href;
  } catch {}
  return null;
}

function allowedRequest(request) {
  const url = new URL(request.url);
  const host = request.headers.get('host');
  if (!/^127\.0\.0\.1:\d+$/.test(host || '') || request.headers.get('sec-fetch-site') === 'cross-site') {
    return false;
  }
  return request.method === 'GET' ||
    (request.method === 'POST' && request.headers.get('origin') === 'http://' + host &&
      url.protocol === 'http:');
}

async function upstream(url, options) {
  return fetch(url, {...options, cache:'no-store', redirect:'error', signal:AbortSignal.timeout(20_000)});
}

function forward(response, body = response.body, headers = new Headers()) {
  for (const name of forwardedHeaders) {
    if (response.headers.has(name)) headers.set(name, response.headers.get(name));
  }
  headers.set('cache-control', 'no-store');
  return new Response(body, {status:response.status, headers});
}

async function directories(folder) {
  try {
    return (await readdir(folder, {withFileTypes:true})).filter(entry => entry.isDirectory());
  } catch (error) {
    if (error.code === 'ENOENT') return [];
    throw error;
  }
}

async function activeRuns() {
  const root = process.env.AXIS_LOCAL_REVIEW_ROOT;
  if (!root || !path.isAbsolute(root)) return [];
  const runs = [];
  const year = path.basename(path.dirname(root));
  for (const source of await directories(root)) {
    const sourceFolder = path.join(root, source.name);
    const label = /^\d{4}$/.test(year) && /^\d{1,2}월$/.test(source.name)
      ? year + ' / ' + source.name : source.name;
    for (const entry of await directories(sourceFolder)) {
      if (!runId.test(entry.name)) continue;
      const folder = path.join(sourceFolder, entry.name);
      try {
        const status = JSON.parse(await readFile(path.join(folder, 'status.json'), 'utf8'));
        if (status.state === 'completed' && status.checks === 'passed' &&
            status.results?.includes(path.join(folder, 'data.sqlite'))) {
          runs.push({id:entry.name, label, folder, result:true});
        } else {
          const view = JSON.parse(await readFile(path.join(folder, 'active-view.json'), 'utf8'));
          const url = loopbackURL(view.url);
          if (/^\/[\w-]{32}\/$/.test(url.pathname) && !url.search) {
            runs.push({id:entry.name, label, url, result:false});
          }
        }
      } catch {
        // An unfinished, closing or malformed run has no view to offer.
      }
    }
  }
  return runs.sort((left, right) => right.id.localeCompare(left.id));
}

function reviewWorkspace(html, run) {
  const prefix = '/local-review/' + run.id + '/';
  const links = [['structure','관계도'], ['headers','헤더 검토'], ['preview','적용 미리보기'],
    ['purposes','업무별 헤더'], ['coverage','폴더 전체 확인']];
  const tabs = links.map(([key, label], index) =>
    `<button type="button" data-view="${key}" class="table-nav-item" aria-current="${index === 0}">${label}</button>`).join('');
  return html
    .replace('<body data-view="combined">', '<body data-view="graph" data-schema-review>')
    .replace('<span class="readonly-label">읽기 전용</span>', '<span id="folder" class="review-folder"></span>')
    .replace(/<div class="view-switch"[^>]*>.*?<\/div>/s,
      `<div class="review-actions">
        <span id="message" role="status"></span>
        <button id="save" type="button" disabled>검토 저장</button>
        <button id="approve" type="button" disabled>이 구조로 확정하고 변환</button>
      </div>`)
    .replace('<span id="dataset-description"></span>', '<span id="counts"></span>')
    .replace(/<nav id="table-nav"[^>]*><\/nav>/,
      `<nav class="axis-review-tabs" aria-label="구조 검토">${tabs}</nav>`)
    .replace('<h2>내역표</h2><button id="catalog-button" type="button">표 안내</button>', '<h2>구조 검토</h2>')
    .replace('파일·업체·현장 <span id="total-count">', '제안한 표 <span id="total-count">')
    .replace('<details id="file-explorer"', '<details open id="file-explorer"')
    .replaceAll('파일·업체·현장 찾기', '표 찾기')
    .replace(/<div class="types">.*?<\/div>/s, '')
    .replace(/<footer class="sidebar-note">.*?<\/footer>/s, '')
    .replace(/<main class="table-pane".*?<\/main>/s,
      `<main class="table-pane" id="table-pane">
        <div class="review-filters" id="filters" hidden>
          <input id="header-search" type="search" aria-label="헤더 또는 원본 표기 검색" placeholder="헤더 또는 원본 표기 검색">
          <label><input type="checkbox" id="issues"> 확인 필요만</label>
          <button id="accept" type="button">근거가 있는 헤더 일괄 적용</button>
        </div>
        <div id="content"></div>
      </main>`)
    .replace('<h2>연결 관계</h2><button id="expand-graph" type="button">크게 보기</button>', '<h2>제안한 표의 관계</h2>')
    .replace('<aside id="inspector"', '<aside tabindex="-1" id="inspector"')
    .replace(/<div class="graph-key">.*?<\/div>/s, '<div class="graph-key"><span><i class="dot file"></i>제안한 표</span></div>')
    .replace('큰 점은 연결 대상이 많습니다. 점을 누르면 목록이 열립니다.', '표나 연결선을 선택하면 원본 근거가 열립니다.')
    .replace(/<script src="\/local-graph\/integrated\.js" defer><\/script>/,
      '')
    .replace('<script src="/local-graph/purpose-navigation.js" defer></script>', '')
    .replace('<script src="/local-graph/graph_engine.js" defer></script>',
      `<script src="${prefix}data.js" defer></script><script src="/graph_engine.js" defer></script>`)
    .replace('<script src="/local-graph/graph3d.js" defer></script>',
      `<script src="/graph3d.js" defer></script><script src="${prefix}controls.js" defer></script>`);
}

function resultURL(run, table = '', view = 'combined') {
  const params = new URLSearchParams({dataset:'review:' + run.id, view});
  if (table) params.set('table', table);
  return '/?' + params;
}

function resultWorkspace(html, run) {
  const resultBootstrap = '/bootstrap.js?dataset=' + encodeURIComponent('review:' + run.id);
  return html
    .replace('<script src="/local-graph/graph_engine.js" defer></script>',
      `<script src="${resultBootstrap}" defer></script><script src="/graph_engine.js" defer></script>`)
    .replace('<script src="/local-graph/integrated.js" defer></script>', '<script src="/integrated.js" defer></script>')
    .replace('<script src="/local-graph/graph3d.js" defer></script>', '<script src="/graph3d.js" defer></script>')
    .replace('<script src="/local-graph/purpose-navigation.js" defer></script>', '<script src="/purpose-navigation.js" defer></script>')
    .replace('파일·업체·현장 <span id="total-count">', '변환된 표 <span id="total-count">')
    .replaceAll('파일·업체·현장 찾기', '표 찾기')
    .replace(/<div class="types">.*?<\/div>/s, '')
    .replace('<h2>연결 관계</h2>', '<h2>테이블 관계</h2>')
    .replace(/<div class="graph-key">.*?<\/div>/s, '<div class="graph-key"><span><i class="dot file"></i>테이블</span></div>')
    .replace('큰 점은 연결 대상이 많습니다. 점을 누르면 목록이 열립니다.', '표를 누르면 저장된 행과 열을 볼 수 있습니다.');
}

export async function localGraph(request, home = false) {
  if (!allowedRequest(request)) return problem('로컬 주소에서 열어 주세요.', 403);
  const current = new URL(request.url);
  const asset = current.pathname.startsWith('/local-graph/')
    ? current.pathname.slice('/local-graph/'.length) : '';
  if (!home && !legacyAsset.test(asset) && !legacyPath.test(current.pathname)) {
    return problem('페이지를 찾을 수 없습니다.', 404);
  }
  try {
    const selection = current.searchParams.get('dataset') || '';
    const requested = selection.startsWith('review:') ? selection.slice('review:'.length)
      : current.searchParams.get('review');
    const runs = home || requested ? await activeRuns() : [];
    const run = runs.find(item => item.id === requested);
    if (home && selection.startsWith('review:') && !run) {
      return problem('검토 화면이 닫혔습니다. MCP에서 작업을 다시 열어 주세요.', 404);
    }
    if (!home && selection.startsWith('review:') && resultRoutes.has(current.pathname)) {
      if (!run?.result) return problem('검증된 SQLite 결과를 찾을 수 없습니다.', 404);
      const datasets = current.pathname === '/bootstrap.js' ? Object.fromEntries(runs.map(item => [
        'review:' + item.id, {label:item.label + (item.result ? ' · 변환 결과' : ' · 구조 검토')},
      ])) : undefined;
      return await localResult(run, current.pathname, current.searchParams, datasets);
    }
    const target = loopbackURL(process.env.AXIS_LOCAL_GRAPH_URL);
    target.pathname = home ? '/' : asset ? '/' + asset : current.pathname;
    target.search = current.search;
    if (selection.startsWith('review:')) target.searchParams.delete('dataset');
    const response = await upstream(target);
    if (!home || !response.ok) return forward(response);
    const html = (await response.text()).replace(/(src|href)="([^"/?]+)(?=[?"])/g,
      (attribute, key, file) => legacyAsset.test(file) ? `${key}="/local-graph/${file}` : attribute);
    const options = runs.map(item => `<option value="review:${item.id}"${run?.id === item.id ? ' selected' : ''}>${escape(item.label)} · ${item.result ? '변환 결과' : '구조 검토'}</option>`).join('');
    const shared = (run?.result ? html : html.replace('id="dataset-select" aria-label="자료 범위"></select>',
        `id="dataset-select" aria-label="자료 범위">${options}</select>`)
      )
      .replace('</head>', '<link rel="stylesheet" href="/local-review.css"><script src="/local-review-nav.js" defer></script></head>');
    return forward(response, run?.result ? resultWorkspace(shared, run) : run ? reviewWorkspace(shared, run) : shared);
  } catch {
    return problem('기존 관계도 서버에 연결할 수 없습니다.', 502);
  }
}

export async function localReview(request) {
  if (!localViewerEnabled()) return problem('페이지를 찾을 수 없습니다.', 404);
  if (!allowedRequest(request)) return problem('로컬 주소에서 열어 주세요.', 403);
  const current = new URL(request.url);
  const [, , id, ...parts] = current.pathname.split('/');
  if (!runId.test(id)) return problem('검토를 찾을 수 없습니다.', 404);
  const section = parts.join('/');
  const prefix = '/local-review/' + id + '/';
  try {
    const runs = (await activeRuns()).filter(run => run.id === id);
    if (runs.length !== 1) return problem('검토 화면이 닫혔습니다. MCP에서 작업을 다시 열어 주세요.', 404);
    const [run] = runs;
    if (request.method === 'POST') {
      if (run.result || !['draft', 'approve'].includes(section)) return problem('저장할 검토가 없습니다.', 409);
      const length = Number(request.headers.get('content-length'));
      if (!(length > 0 && length <= 4_000_000) ||
          request.headers.get('content-type') !== 'application/json') {
        return problem('검토 저장 요청을 확인해 주세요.', 400);
      }
      return forward(await upstream(new URL(section, run.url), {method:'POST',
        headers:{'content-type':'application/json', origin:run.url.origin},
        body:await request.arrayBuffer()}));
    }
    if (run.result) {
      const result = resultURL(run, current.searchParams.get('table'));
      if (section === 'status') return Response.json({approved:true, finished:true, result},
        {headers:{'cache-control':'no-store'}});
      if (!section || section === 'result/') {
        return new Response(null, {status:307, headers:{location:result, 'cache-control':'no-store'}});
      }
      if (section === 'result/csv' || section === 'result/sql') {
        return await localResult(run, section.slice('result'.length), current.searchParams);
      }
      return problem('결과를 찾을 수 없습니다.', 404);
    }
    if (section === 'data.js') {
      // The running Python review owns the current draft, including saves from other tabs.
      const page = await upstream(run.url);
      const embedded = (await page.text()).match(/^const \{proposal, decisions, folder\} = (.+);\r?$/m);
      if (!page.ok || !embedded) return problem('검토 데이터를 읽을 수 없습니다.', 502);
      const data = JSON.parse(embedded[1]);
      const nodes = data.proposal.tables.map((table, index, tables) => {
        const angle = 2 * Math.PI * index / tables.length;
        return {id:table.name, label:table.label, kind:'table',
          x:180 * Math.cos(angle), y:180 * Math.sin(angle)};
      });
      const edges = (data.proposal.relationships || []).map((edge, index) => ({
        id:'edge-' + index, from:edge.from_table, to:edge.to_table, status:'observed',
        label:'표 연결', note:edge.reason, evidence:[],
      }));
      const graph = {nodes, edges, counts:{tables:nodes.length}};
      return reviewJavascript(`window.AXIS_REVIEW_DATA=${JSON.stringify(data)};
window.AXIS_REVIEW_BASE=${JSON.stringify(prefix)};window.GRAPH_DATA=${JSON.stringify(graph)};`);
    }
    if (section === 'controls.js') {
      const template = await readFile(path.resolve(process.cwd(), '../scripts/review_headers.html'), 'utf8');
      const controls = template.split('<script>')[1]?.split('</script>')[0];
      if (!controls) return problem('검토 기능을 불러올 수 없습니다.', 502);
      return reviewJavascript(`(() => {
if (!window.AXIS_REVIEW_DATA) {
  document.getElementById('message').textContent = '검토 데이터를 불러오지 못했습니다. 페이지를 새로고침하세요.';
  return;
}
${controls.replace('/* AXIS_DATA */', 'window.AXIS_REVIEW_DATA')}
})();`);
    }
    if (section && section !== 'status' && !section.startsWith('source/')) {
      return problem('검토 페이지를 찾을 수 없습니다.', 404);
    }
    // Keep the capability URL and any source paths inside this review session.
    const target = new URL(run.url);
    target.pathname += section;
    const response = await upstream(target);
    if (section !== 'status' || !response.ok) return forward(response);
    const status = await response.json();
    if (status.result && !hostedResultURL(status.result)) status.result = resultURL(run);
    return Response.json(status, {headers:{'cache-control':'no-store'}});
  } catch {
    return problem('검토 서버에 연결할 수 없습니다.', 502);
  }
}

function reviewJavascript(body) {
  return new Response(body, {headers:{'content-type':'text/javascript; charset=utf-8',
    'cache-control':'no-store', 'x-content-type-options':'nosniff'}});
}
