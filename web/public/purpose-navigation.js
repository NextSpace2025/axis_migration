// Adapter for integrated graph viewers exposing APP_META and integratedView.
(() => {
  const meta = window.APP_META;
  const viewer = window.integratedView;
  const nav = document.getElementById('table-nav');
  if (!meta || !viewer || !nav || document.getElementById('purpose-list')) return;
  const entries = [];
  for (const table of meta.tables) {
    const proposed = meta.catalog.purpose_tables?.find(t => t.name === table.name);
    if (proposed) {
      for (const p of proposed.purposes) entries.push({table, label:p.question, basis:p.basis,
        headers:p.headers.map(i => proposed.mappings[i].label), gaps:p.gaps,
        files:new Set(p.headers.flatMap(i => proposed.mappings[i].files))});
    } else if (table.group !== '출처와 검토' && table.columns.length) {
      entries.push({table, label:table.title, basis:table.guide.interpretation || table.guide.why,
        headers:table.columns.map(c => c.label || c.name), gaps:[table.guide.caution].filter(Boolean)});
    }
  }
  if (!entries.length) return;
  const list = document.createElement('details');
  list.id = 'purpose-list';
  list.open = true;
  const summary = document.createElement('summary');
  summary.textContent = '업무별 헤더';
  list.append(summary);
  nav.before(list);
  const dialog = document.createElement('dialog');
  dialog.id = 'purpose-headers';
  dialog.setAttribute('aria-labelledby', 'purpose-headers-title');
  const style = document.createElement('style');
  style.textContent = `
    #purpose-headers {
      width: min(34rem, calc(100% - 2rem));
      max-height: 80vh;
      padding: 1.25rem;
      box-sizing: border-box;
      color: var(--text, CanvasText);
      background: var(--pane, Canvas);
      border: 1px solid var(--line, GrayText);
      border-radius: .75rem;
    }
    #purpose-headers::backdrop { background: rgb(0 0 0 / .55); }
    #purpose-headers h2 { margin: .3rem 0 1rem; }
    #purpose-headers ol { margin: 0 0 1.25rem; padding-inline-start: 2rem; }
    #purpose-headers li { padding: .45rem .25rem; border-bottom: 1px solid var(--line, GrayText); }
    #purpose-headers footer { display: flex; justify-content: flex-end; gap: .5rem; }
  `;
  document.head.append(style);
  document.body.append(dialog);
  function button(parent, text, action) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'table-nav-item';
    b.textContent = text;
    b.onclick = action;
    parent.append(b);
    return b;
  }
  function show(entry) {
    dialog.replaceChildren();
    const title = document.createElement('h2');
    title.id = 'purpose-headers-title';
    title.textContent = entry.label + ' · 헤더 구성';
    const headers = document.createElement('ol');
    for (const label of entry.headers) {
      const header = document.createElement('li');
      header.textContent = label;
      headers.append(header);
    }
    const actions = document.createElement('footer');
    button(actions, '관련 표 보기', () => {
      dialog.close();
      showTable(entry);
    });
    const close = button(actions, '닫기', () => dialog.close());
    dialog.append(title, headers, actions);
    dialog.showModal();
    close.focus();
  }
  function showTable(entry) {
    viewer.setMode('combined');
    viewer.selectTable(entry.table.name);
    const guide = document.getElementById('table-guide');
    guide.open = true;
    const box = document.getElementById('guide-content');
    const explanation = document.createElement('section');
    for (const text of [entry.label, entry.basis, entry.table.guide.row_meaning, ...entry.gaps].filter(Boolean)) {
      const p = document.createElement('p');
      p.textContent = text;
      explanation.append(p);
    }
    box.prepend(explanation);
    if (entry.files) {
      for (const n of window.graphView.nodes.values()) {
        if (supportsFile(entry, n)) button(explanation, n.label, () => window.graphView.selectNode(n.id, {local:false}));
      }
    }
  }
  function supportsFile(entry, n) {
    return n?.kind === 'file' && [n.relativePath, n.sourcePath].some(path =>
      path && entry.files.has(path.replaceAll('\\', '/')));
  }
  for (const entry of entries) button(list, entry.label, () => show(entry));
  let current;
  async function related(node) {
    current?.abort();
    const controller = new AbortController();
    current = controller;
    const pane = document.getElementById('inspector');
    pane.querySelector('[data-purpose-links]')?.remove();
    if (window.graphView.nodes.get(node)?.kind !== 'file') return;
    const section = document.createElement('section');
    section.dataset.purposeLinks = '';
    const heading = document.createElement('h3');
    heading.textContent = '이 파일로 살펴볼 업무';
    section.append(heading);
    pane.append(section);
    try {
      for (const table of new Set(entries.map(e => e.table))) {
        const purposes = entries.filter(e => e.table === table);
        if (purposes.every(e => e.files)) {
          for (const e of purposes.filter(e => supportsFile(e, window.graphView.nodes.get(node)))) {
            button(section, e.label, () => show(e));
          }
          continue;
        }
        const params = new URLSearchParams({dataset:meta.dataset, table:table.name, node, size:'100'});
        for (let page = 0; ; page++) {
          params.set('page', page);
          const response = await fetch('/api/rows?' + params, {signal:controller.signal});
          if (!response.ok) throw Error();
          const batch = await response.json();
          if (batch.rows.some(row => row.binding.node_ids.includes(node))) {
            for (const entry of purposes) button(section, entry.label, () => show(entry));
            break;
          }
          if ((page + 1) * 100 >= batch.total) break;
        }
      }
      if (section.children.length === 1) section.append('원본 행과 연결된 업무를 찾지 못했습니다.');
    } catch (error) {
      if (!controller.signal.aborted) section.append('연결된 원본 행을 읽을 수 없습니다.');
    }
  }
  document.addEventListener('axis:graph-selection', event => {
    related(event.detail.edge ? null : event.detail.node);
  });
  related(window.graphView.state.node);
})();
