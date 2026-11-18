(() => {
 'use strict';
 const meta=window.APP_META,$=id=>document.getElementById(id),tables=new Map(meta.tables.map(t=>[t.name,t]));
 const query=new URLSearchParams(location.search);
 const state={table:tables.has(query.get('table'))?query.get('table'):meta.default_table,page:0,size:50,q:'',node:window.graphView?.state.node||'',row:null,mode:'combined',catalog:query.get('view')==='dashboard',sequence:0};
 let suppress=false,debounce;
 const el=(tag,cls,text)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined)e.textContent=text;return e;};
 const btn=(text,fn,cls='')=>{const b=el('button',cls,text);b.type='button';b.addEventListener('click',fn);return b;};
 const link=(text,url,cls='')=>{const a=el('a',cls,text);a.href=url;a.target='_blank';a.rel='noopener';return a;};
 const qs=o=>new URLSearchParams(Object.entries(o).filter(([,v])=>v!==''&&v!==null&&v!==undefined));
 const api=(route,extra={})=>route+'?'+qs({dataset:meta.dataset,table:state.table,...extra});
 async function fetchJSON(url){const r=await fetch(url);const d=await r.json();if(!r.ok)throw Error(d.error||'자료를 읽지 못했습니다.');return d;}
 const compact=(value,max=95)=>{const s=String(value??'');return s.length>max?s.slice(0,max)+'…':s;};
 const valueText=v=>v===null?'—':v===''?'빈 문자열':typeof v==='string'&&!v.trim()?'공백 '+v.length+'자':String(v);
 const count=n=>String(n).replace(/\B(?=(\d{3})+(?!\d))/g,',');
 function updateURL(){const p=qs({dataset:meta.dataset,table:state.table,view:state.catalog?'dashboard':state.mode});history.replaceState(null,'','?'+p+location.hash);}
 function setMode(mode){state.mode=mode;document.body.dataset.view=mode;document.querySelectorAll('.view-switch button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.view===mode)));$('expand-graph').textContent=mode==='graph'?'표와 함께':'크게 보기';if(mode==='graph')$('file-explorer').open=true;updateURL();requestAnimationFrame(()=>window.graphView?.fit());}
 function nav(){const target=$('table-nav');target.replaceChildren();const groupNames=[...new Set(meta.tables.map(t=>t.group))];const reviewGroup="출처와 검토";const orderedGroups=[...groupNames.filter(group=>group!==reviewGroup),...groupNames.filter(group=>group===reviewGroup)];for(const group of orderedGroups){target.append(el('p','nav-group',group));for(const t of meta.tables.filter(x=>x.group===group)){const b=btn('',()=>selectTable(t.name),'table-nav-item'+(!state.catalog&&state.table===t.name?' active':''));b.dataset.table=t.name;b.append(el('span','',t.title),el('span','nav-count',count(t.count)));target.append(b);}}}
 function renderNotice(){const notices=meta.catalog.notices||[];$('dataset-notice').hidden=!notices.length;$('dataset-notice').textContent=notices.map(n=>n.title+' · '+n.text).join(' ');}
 function guide(){const t=tables.get(state.table),box=$('guide-content');box.replaceChildren();for(const [label,key]of [['한 행의 의미','row_meaning'],['살펴볼 내용','why'],['읽을 때 주의','caution']])if(t.guide[key]){const p=el('p');p.append(el('strong','',label+' · '),document.createTextNode(t.guide[key]));box.append(p);}for(const c of t.columns){const part=el('div','guide-column');part.append(el('strong','',c.label||c.name),el('small','',c.name),el('p','',c.description||'저장된 원문 값입니다.'));if(c.unit&&c.unit!=='해당 없음')part.append(el('p','','단위 · '+c.unit));if(c.notes)part.append(el('p','',c.notes));box.append(part);}}
 function scopeChip(){const n=window.graphView?.nodes.get(state.node);$('source-filter').hidden=meta.localResult||!n;$('filter-label').textContent=n?'연결된 파일 기준 · '+n.label:'';}
 function columnHelp(c){const pane=$('inspector');pane.replaceChildren(el('h2','',c.label||c.name),el('p','row-description','컬럼 설명 · '+c.name));const d=el('dl','row-values');for(const [label,value]of [['뜻',c.description],['단위',c.unit],['읽을 때 주의',c.notes],['근거',c.unit_basis]])if(value){d.append(el('dt','',label),el('dd','',value));}pane.append(d);}
 function cellPreview(value){const wrapper=el('div','cell-preview');try{const cells=JSON.parse(value);if(Array.isArray(cells)){for(const x of cells.slice(0,3)){const line=el('span');line.append(el('code','',x.cell||''),document.createTextNode(compact(x.value,70)));wrapper.append(line);}if(cells.length>3)wrapper.append(el('small','','+'+(cells.length-3)+'개 셀 · 행을 선택해 전체 보기'));return wrapper;}}catch{}wrapper.append(el('span','',compact(value,120)));return wrapper;}
 function drawRows(result){const table=$('data-table'),head=table.querySelector('thead'),body=table.querySelector('tbody');table.classList.toggle('compact-raw',state.table==='extracted_row');head.replaceChildren();body.replaceChildren();const header=el('tr');for(const c of result.columns){const th=el('th');th.scope='col';const b=btn('',()=>columnHelp(c),'column-help');b.append(el('span','',c.label||c.name),el('small','',c.name));if(c.unit&&c.unit!=='해당 없음'&&c.unit!=='원문 기준')b.append(el('small','','단위 '+c.unit));th.append(b);header.append(th);}head.append(header);
  for(const row of result.rows){const tr=el('tr',state.row?.key===row.key?'selected':'');tr.dataset.key=row.key;tr.addEventListener('click',()=>selectRow(row));for(let index=0;index<result.columns.length;index++){const c=result.columns[index],v=row.values[c.name],td=el('td');td.title=valueText(v);if(index===0){const b=btn(valueText(v),ev=>{ev.stopPropagation();selectRow(row);},'pick-row');b.setAttribute('aria-label','행 '+row.key+' 선택');td.append(b);}else if(c.name==='cell_json')td.append(cellPreview(v));else if(c.name==='unit_id'&&row.binding.sources.length){td.className='unit-context';td.append(el('span','context-name',row.binding.sources[0].label),el('span','context-location',(row.binding.unit_name||'원문 단위')+' · #'+v));}else if(v!==null&&typeof v==='string'&&v.length>140){td.append(el('span','',compact(v,120)),el('span','context-location','선택하면 전체 값을 볼 수 있습니다'));}else td.append(el('span',v===null||v===''?'muted-value':'',valueText(v)));tr.append(td);}body.append(tr);}
  $('table-empty').hidden=result.rows.length>0;$('table-empty').textContent='조건에 맞는 행이 없습니다. 검색어나 연결된 파일 선택을 해제해 보세요.';
  $('table-status').textContent='총 '+count(result.total)+'행'+(state.q?' · 검색 결과':'')+(state.node?' · 연결된 파일로 좁혀 보기':'');
  const start=result.total?state.page*state.size+1:0,end=Math.min((state.page+1)*state.size,result.total);$('page-label').textContent=count(start)+'–'+count(end)+' / '+count(result.total);$('page-prev').disabled=state.page===0;$('page-next').disabled=end>=result.total;
 }
 async function loadRows(){if(state.catalog)return renderCatalog();const seq=++state.sequence;const t=tables.get(state.table);$('table-title').textContent=t.title;$('table-subtitle').textContent=state.table+' · 기존 저장값';$('data-grid').hidden=false;$('catalog-panel').hidden=true;$('table-guide').hidden=false;document.querySelector('.table-pager').hidden=false;document.querySelector('.table-actions').hidden=false;$('table-status').textContent='자료를 불러오는 중입니다…';$('table-status').setAttribute('aria-busy','true');$('data-table').querySelector('tbody').replaceChildren();scopeChip();guide();nav();updateURL();
  $('csv-link').href=api('/csv',{q:state.q,node:state.node});
  if(meta.localResult&&$('sql-link'))$('sql-link').href=api('/sql');
  try{const result=await fetchJSON(api('/api/rows',{page:state.page,size:state.size,q:state.q,node:state.node}));if(seq!==state.sequence)return;drawRows(result);}catch(error){if(seq!==state.sequence)return;$('table-empty').hidden=false;$('table-empty').replaceChildren(el('p','',error.message),btn('다시 읽기',loadRows));$('table-status').textContent='표를 읽지 못했습니다.';}finally{if(seq===state.sequence)$('table-status').setAttribute('aria-busy','false');}
 }
 function selectTable(name){if(!tables.has(name))return;state.table=name;state.catalog=false;state.page=0;state.row=null;if(state.mode==='graph')setMode('combined');document.body.classList.remove('nav-open');$('nav-toggle').setAttribute('aria-expanded','false');loadRows();}
 function detailValues(detail){const pane=$('inspector');pane.replaceChildren(el('h2','',detail.binding.source_row?'원본 '+detail.binding.source_row+'행':'선택한 행 #'+detail.key),el('p','row-context',tables.get(detail.table).title),el('p','row-description','원문 값과 기존 DB 값을 그대로 보여줍니다. 값을 수정하거나 관계를 확정하지 않습니다.'));const actions=el('div','detail-actions');actions.append(btn('관계도에서 보기',()=>{setMode('graph');if(detail.binding.node_ids[0])window.graphView.selectNode(detail.binding.node_ids[0],{local:!window.graph3D});}),btn('값 복사',async()=>{try{await navigator.clipboard.writeText(JSON.stringify(detail.values,null,2));$('toast').textContent='기존 저장값을 복사했습니다.';$('toast').hidden=false;setTimeout(()=>$('toast').hidden=true,2000);}catch{$('toast').textContent='값을 선택해 직접 복사해 주세요.';$('toast').hidden=false;}}));pane.append(actions);
  if(detail.binding.sources.length){const sec=el('section');sec.append(el('h3','','원문 위치'));for(const source of detail.binding.sources){const block=el('div','source-link-block');if(source.url)block.append(link(meta.dataset==='prior'?'원문 추출 기록 보기':'원본 위치 열기',source.url));block.append(el('small','',source.label),el('small','',source.location||'문서 범위 근거'));sec.append(block);}pane.append(sec);}else pane.append(el('p','row-description','이 행의 파일 연결은 미확정입니다. 아래 원문 근거 필드를 확인해 주세요.'));
  const sec=el('section');sec.append(el('h3','','이 행의 값'));const dl=el('dl','row-values');for(const c of detail.columns){const v=detail.values[c.name],dt=el('dt','',c.label||c.name);dt.append(el('code','',c.name));dl.append(dt);const dd=el('dd');if(c.name==='cell_json'){try{const cells=JSON.parse(v);if(Array.isArray(cells)){const grid=el('div','raw-cell-grid');for(const x of cells)grid.append(el('code','',x.cell),el('span','',valueText(x.value)));dd.append(grid);}else dd.textContent=valueText(v);}catch{dd.textContent=valueText(v);}}else dd.textContent=valueText(v);dl.append(dd);}sec.append(dl);pane.append(sec);if(matchMedia('(max-width:760px)').matches)pane.scrollIntoView({block:'start',behavior:matchMedia('(prefers-reduced-motion:reduce)').matches?'instant':'smooth'});
 }
 async function selectRow(row){const table=state.table;state.row={key:row.key,table};document.querySelectorAll('#data-table tbody tr').forEach(tr=>tr.classList.toggle('selected',tr.dataset.key===row.key));try{const detail=await fetchJSON(api('/api/detail',{key:row.key}));if(state.table!==table||state.row?.key!==row.key)return;const node=detail.binding.node_ids[0];if(node){suppress=true;window.graphView.selectNode(node,{local:!window.graph3D});suppress=false;}detailValues(detail);}catch(error){$('inspector').replaceChildren(el('p','error-note',error.message));}}
 function graphSelection(event){if(suppress)return;const selection=event.detail;if(meta.localResult){if(selection.node&&!selection.edge)selectTable(selection.node);return;}state.row=null;document.querySelectorAll('#data-table tbody tr.selected').forEach(tr=>tr.classList.remove('selected'));if(selection.edge){addRelatedButton(selection.node);return;}state.node=selection.node||'';state.page=0;loadRows();addRelatedButton(state.node);}
 function addRelatedButton(node){if(!node)return;const pane=$('inspector');pane.querySelector('.related-rows')?.remove();pane.prepend(btn('관련 행 보기',()=>{state.node=node;state.page=0;state.catalog=false;setMode('combined');loadRows();},'related-rows'));}
 function renderCatalog(){state.sequence++;nav();$('table-title').textContent='표 안내';$('table-subtitle').textContent=meta.tables.length+'개 표의 한 행 의미와 원문 근거';$('data-grid').hidden=true;$('catalog-panel').hidden=false;$('table-guide').hidden=true;$('source-filter').hidden=true;document.querySelector('.table-pager').hidden=true;document.querySelector('.table-actions').hidden=true;$('table-status').textContent='기존 표를 선택해 원문과 관계를 함께 확인하세요.';const box=$('catalog-panel');box.replaceChildren();for(const t of meta.tables){const item=el('article','catalog-entry'),head=el('header');head.append(el('h3','',t.title),el('span','count',count(t.count)+'행'));item.append(head,el('p','',t.guide.why||t.guide.row_meaning),el('p','',t.guide.caution),btn('이 표 열기',()=>selectTable(t.name)));box.append(item);}updateURL();}
 window.integratedIdleInspector=pane=>{pane.replaceChildren();pane.append(el('h2','','표에서 한 행을 선택하세요'),el('p','subtext','연결된 파일을 관계도에서 확인하고, 원문 위치와 저장값을 함께 살펴볼 수 있습니다.'));const sec=el('section');sec.append(el('h3','','확인과 추정을 구분합니다'),el('p','subtext',meta.dataset==='prior'?'이 자료의 관계는 기존 부분 변환 DB의 기록에서 가져온 후보입니다. 원문을 새로 판독하거나 거래를 확정하지 않았습니다.':'실선은 원문 표기·수식·동일 파일 등으로 확인한 연결이고, 점선은 추정·미확정 관계입니다.'));pane.append(sec);};
 if(meta.localResult)window.integratedIdleInspector=pane=>pane.replaceChildren(el('h2','','검증된 변환 결과'),el('p','subtext','행을 선택하면 저장값과 원본 위치를 볼 수 있습니다. 관계도의 선은 SQLite 외래 키입니다.'));
 for(const [key,info]of Object.entries(meta.datasets)){const o=el('option','',info.label);o.value=key;$('dataset-select').append(o);}$('dataset-select').value=meta.dataset;$('dataset-description').textContent=meta.datasets[meta.dataset].description;
 $('dataset-select').addEventListener('change',ev=>{location.href='/?'+qs({dataset:ev.target.value,table:meta.datasets[ev.target.value].default_table,view:state.mode});});
 document.querySelectorAll('.view-switch button').forEach(b=>b.addEventListener('click',()=>setMode(b.dataset.view)));$('expand-graph').addEventListener('click',()=>setMode(state.mode==='graph'?'combined':'graph'));
 $('table-search').addEventListener('input',ev=>{state.q=ev.target.value;state.page=0;state.catalog=false;clearTimeout(debounce);debounce=setTimeout(loadRows,220);});
 $('page-prev').addEventListener('click',()=>{if(state.page){state.page--;loadRows();}});$('page-next').addEventListener('click',()=>{state.page++;loadRows();});$('page-size').addEventListener('change',ev=>{state.size=+ev.target.value;state.page=0;loadRows();});
 $('clear-source-filter').addEventListener('click',()=>{state.node='';state.page=0;loadRows();});$('catalog-button').addEventListener('click',()=>{state.catalog=true;if(state.mode==='graph')setMode('combined');renderCatalog();});
 $('nav-toggle').addEventListener('click',()=>$('nav-toggle').setAttribute('aria-expanded',String(document.body.classList.toggle('nav-open'))));
 document.addEventListener('axis:graph-selection',graphSelection);
 renderNotice();nav();setMode(['table','graph','combined'].includes(query.get('view'))?query.get('view'):'combined');
 if(!window.graphView.state.node&&!window.graphView.state.edge)window.integratedIdleInspector($('inspector'));
 loadRows();window.integratedView={state,selectTable,loadRows,setMode};
})();

;(() => {
  const control = document.getElementById('viewer-theme');
  if (!control) return;
  const key = 'axis-viewer-theme';
  function apply(value) {
    const theme = value === 'light' ? 'light' : 'dark';
    document.documentElement.dataset.theme = theme;
    control.value = theme;
    document.dispatchEvent(new Event('axis:theme-change'));
  }
  let savedTheme;
  try { savedTheme = localStorage.getItem(key); } catch {}
  apply(savedTheme);
  control.addEventListener('change', () => {
    apply(control.value);
    try { localStorage.setItem(key, control.value); } catch {}
  });
  window.addEventListener('storage', event => {
    if (event.key === key || event.key === null) apply(event.newValue);
  });
})();

;
