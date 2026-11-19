export const headerContents = `<div class="brand"><svg viewBox="0 0 30 30" width="30" height="30" aria-hidden="true"><path d="M7 8L22 15L10 24M7 8L10 24" fill="none" stroke="currentColor" stroke-width="1.5"/><circle cx="7" cy="8" r="4" fill="currentColor"/><circle cx="22" cy="15" r="3.5" fill="currentColor"/><circle cx="10" cy="24" r="3" fill="currentColor"/></svg><div><h1>axis_migration</h1></div></div><select id="viewer-theme" aria-label="화면 모드"><option value="dark">다크 모드</option><option value="light">라이트 모드</option></select><a class="text-action" href="/documents">문서 분석</a><a class="text-action" href="/results">조회 번호 입력</a>`;
export function entryPage(title, content) {
  return `<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>${title} · axis_migration</title><link rel="stylesheet" href="/graph.css"><link rel="stylesheet" href="/integrated.css"><link rel="stylesheet" href="/analysis-view.css"><script defer src="/analysis-theme.js"></script></head>
    <body><header class="app-header">${headerContents}</header><div class="app-subbar"><span>자료 탐색</span></div>
    <div class="workspace integrated-workspace analysis-workspace"><aside class="sidebar app-sidebar"><div class="nav-heading"><h2>자료 범위</h2></div><nav><a href="/documents">문서 분석</a><a href="/results">저장된 결과</a></nav></aside>
    <main class="table-pane"><header class="table-heading"><h2>${title}</h2></header>${content}</main>
    <section class="graph-pane graph-panel"><header class="panel-heading"><h2>연결 관계</h2></header><p class="analysis-empty">자료를 열면 연결 관계를 볼 수 있습니다.</p></section>
    <aside class="inspector detail-pane"><h2>원문 근거</h2><p class="subtext">분석 결과에서 관계를 선택하면 출처가 표시됩니다.</p></aside></div></body></html>`;
}
