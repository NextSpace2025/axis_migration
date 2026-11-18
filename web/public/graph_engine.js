(() => {
  'use strict';
  const data=window.GRAPH_DATA;
  const $=id=>document.getElementById(id);
  if(!data){$('inspector').textContent='연결 자료를 읽지 못했습니다. 같은 폴더의 graph-data.js를 확인한 뒤 새로고침하세요.';return;}
  const nodes=new Map(data.nodes.map(n=>[n.id,{...n}]));
  const edges=new Map(data.edges.map(e=>[e.id,e]));
  const adjacency=new Map(data.nodes.map(n=>[n.id,[]]));
  data.edges.forEach(e=>{adjacency.get(e.from)?.push(e);if(e.to!==e.from)adjacency.get(e.to)?.push(e);});
  const state={node:null,edge:null,kind:'all',query:'',status:'all',local:false,history:[],visibleNodes:[],visibleEdges:[]};
  const kindNames={file:'파일',company:'업체 원문 표기',site:'현장·차수 원문 표기',expected:'미발견 첨부자료',table:'표'};
  const norm=s=>String(s||'').toLocaleLowerCase().replace(/\s/g,'');
  const element=(tag,cls,text)=>{const e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined)e.textContent=text;return e;};
  const button=(text,fn,cls='')=>{const e=element('button',cls,text);e.type='button';e.addEventListener('click',fn);return e;};
  const estimated=e=>e.status!=='observed';
  const statusText=e=>e.status==='observed'?'확인':e.status==='candidate'?'추정':'미확정';
  const badge=e=>element('span','status '+(estimated(e)?'estimated':'observed'),statusText(e));
  const dot=kind=>element('i','dot '+(kind==='expected'?'file':kind));
  const sourceHref=r=>{const q=new URLSearchParams({id:r.source_id,dataset:window.APP_META.dataset});if(r.page)q.set('page',r.page);if(r.sheet)q.set('sheet',r.sheet);if(r.cell)q.set('cell',r.cell);return 'source.html?'+q;};
  const link=(text,href)=>{const a=element('a','',text);a.href=href;a.target='_blank';a.rel='noopener';return a;};
  const section=title=>{const s=element('section');s.append(element('h3','',title));return s;};
  const nodeLink=id=>button(nodes.get(id)?.label||id,()=>selectNode(id),'node-link');
  function saveSelection(){const q=new URLSearchParams();if(state.edge)q.set('edge',state.edge);else if(state.node)q.set('node',state.node);history.replaceState(null,'','#'+q);}
  function remember(){state.history.push({node:state.node,edge:state.edge,local:state.local});$('back').disabled=false;}
  function selectNode(id,opts={}){
    if(!nodes.has(id))return;
    if(!opts.noHistory&&(id!==state.node||state.edge))remember();
    state.node=id;state.edge=null;if(opts.local!==undefined)state.local=opts.local;
    $('local').disabled=false;$('local').setAttribute('aria-pressed',String(state.local));
    render();if(state.local)fit();saveSelection();document.dispatchEvent(new CustomEvent('axis:graph-selection',{detail:{node:state.node,edge:state.edge}}));
    if(window.innerWidth<=900){document.body.classList.remove('list-open');$('mobile-list').setAttribute('aria-expanded','false');}
  }
  function selectEdge(id,opts={}){if(!edges.has(id))return;if(!opts.noHistory&&id!==state.edge)remember();state.edge=id;if(!state.node){state.node=edges.get(id).from;state.local=true;$('local').disabled=false;$('local').setAttribute('aria-pressed','true');}render();if(state.local)fit();saveSelection();document.dispatchEvent(new CustomEvent('axis:graph-selection',{detail:{node:state.node,edge:state.edge}}));}
  function activeEdges(){return data.edges.filter(e=>!e.internal&&(state.status==='all'||(state.status==='observed'?!estimated(e):estimated(e))));}
  function visible(){
    let ee=activeEdges(),ids=new Set(data.nodes.map(n=>n.id));
    if(state.status!=='all')ids=new Set(ee.flatMap(e=>[e.from,e.to]));
    const query=norm(state.query);
    if(query){const matched=new Set(data.nodes.filter(n=>norm(n.label+' '+(n.relativePath||'')+' '+(n.rawLabel||'')).includes(query)).map(n=>n.id));ids=new Set(matched);ee.forEach(e=>{if(matched.has(e.from)||matched.has(e.to)){ids.add(e.from);ids.add(e.to);}});}
    if(state.local&&state.node){const local=new Set([state.node]);ee.forEach(e=>{if(e.from===state.node)local.add(e.to);if(e.to===state.node)local.add(e.from);});ids=new Set([...ids].filter(id=>local.has(id)));}
    ee=ee.filter(e=>ids.has(e.from)&&ids.has(e.to));
    state.visibleNodes=[...nodes.values()].filter(n=>ids.has(n.id));state.visibleEdges=ee;
  }
  function renderList(){
    const q=norm(state.query);const list=[...nodes.values()].filter(n=>(state.kind==='all'||n.kind===state.kind)&&(!q||norm(n.label+' '+(n.relativePath||'')+' '+(n.rawLabel||'')).includes(q))).sort((a,b)=>a.label.localeCompare(b.label,'ko'));
    $('node-list').replaceChildren();$('list-count').textContent=`${list.length}개 자료`;
    if(!list.length){$('node-list').append(element('p','no-results','일치하는 자료가 없습니다. 다른 업체명이나 파일명 일부로 검색해 보세요.'));return;}
    for(const n of list){const row=button('',()=>selectNode(n.id),'node-row'+(state.node===n.id?' selected':''));row.dataset.nodeId=n.id;row.append(dot(n.kind));const text=element('span','name',n.label);if(n.kind==='file'){const folder=n.relativePath?.includes('\\')?n.relativePath.slice(0,n.relativePath.lastIndexOf('\\')):n.archiveParent?'ZIP 내부 문서':'';if(folder)text.append(element('span','folder',folder));}else text.append(element('span','folder',kindNames[n.kind]));row.append(text);row.setAttribute('aria-label',kindNames[n.kind]+' '+n.label);$('node-list').append(row);}
  }
  function fit(){window.graph3D?.fit();}
  function describeEdge(edge){return [nodes.get(edge.from)?.label,nodes.get(edge.to)?.label].join(' ↔ ')+' · '+edge.label+' · '+statusText(edge);}
  function renderGraph(){
    visible();
    $('graph-empty').hidden=state.visibleNodes.length>0;
    $('visible-count').textContent=`${state.visibleNodes.length}개 점 · ${state.visibleEdges.length}개 연결`;
    document.dispatchEvent(new CustomEvent('axis:graph-render'));
  }
  function evidenceBlock(r){const block=element('div','evidence');block.append(element('p','quote',r.quote||r.basis||'원문 위치 확인'));let loc=r.source_name||nodes.get(r.source_id)?.relativePath||r.source_id;if(r.page)loc+=' · '+r.page+'쪽';if(r.sheet)loc+=' · 시트 '+r.sheet;if(r.cell)loc+=' · '+r.cell;if(r.precision==='document')loc+=' · 문서 범위 근거';block.append(element('p','location',loc));if(r.annotation&&r.annotation!==r.quote)block.append(element('p','location',r.annotation));if(r.source_id)block.append(link('이 원본 위치 보기',sourceHref(r)));return block;}
  function relationButton(e,currentId){const other=e.from===currentId?e.to:e.from;const row=button('',()=>selectEdge(e.id),'relation-row');row.dataset.relationId=e.id;row.append(element('div','relation-title',e.internal?'파일 내부 문서 연결':nodes.get(other)?.label||'첨부자료'));const meta=element('div','relation-meta');meta.append(badge(e),element('span','',e.label));row.append(meta);return row;}
  function relatedItems(id){
    const groups=new Map([['table','테이블'],['file','파일'],['company','업체'],['site','현장'],['expected','첨부자료'],['internal','파일 안의 연결']].map(([kind,title])=>[kind,{title,items:[]}]));
    for(const edge of adjacency.get(id)||[]){
      if(state.status!=='all'&&(state.status==='observed')===estimated(edge))continue;
      const other=nodes.get(edge.from===id?edge.to:edge.from);
      const group=groups.get(edge.internal?'internal':other?.kind)||groups.get('expected');
      group.items.push({edge,label:other?.label||edge.label});
    }
    const panel=section('직접 연결된 자료');
    panel.className='related-items';
    for(const {title,items} of groups.values()){
      if(!items.length)continue;
      items.sort((a,b)=>Number(estimated(a.edge))-Number(estimated(b.edge))||a.label.localeCompare(b.label,'ko'));
      const heading=element('h4','related-category',`${title} ${items.length}건`);
      const list=element('ul','related-list');
      for(const {edge} of items){const item=element('li','');item.append(relationButton(edge,id));list.append(item);}
      panel.append(heading,list);
    }
    if(panel.childElementCount===1)panel.append(element('p','subtext','현재 조건에 맞는 직접 연결이 없습니다.'));
    return panel;
  }
  function renderInspector(){
    const pane=$('inspector');pane.replaceChildren();
    if(!state.node&&!state.edge&&window.integratedIdleInspector){window.integratedIdleInspector(pane);return;}
    if(state.edge){const e=edges.get(state.edge);pane.append(element('h2','',e.label),element('p','row-context','연결 근거'));const endpoints=element('div','selection-line relation-endpoints');endpoints.append(nodeLink(e.from),nodeLink(e.to));pane.append(endpoints,badge(e),element('p','subtext',e.note||'등록된 연결 설명이 없습니다.'));const sec=section('연결에 사용한 근거');if(!e.evidence.length)sec.append(element('p','subtext','등록된 원문 근거가 없습니다.'));for(const r of e.evidence.slice(0,12))sec.append(evidenceBlock(r));if(e.evidence.length>12)sec.append(button('나머지 근거 '+(e.evidence.length-12)+'곳 보기',ev=>{ev;for(const r of e.evidence.slice(12))sec.insertBefore(evidenceBlock(r),sec.lastChild);sec.lastChild.remove();}));pane.append(sec);return;}
    const n=nodes.get(state.node);
    if(!n){pane.append(element('h2','','파일 사이의 맥락을 보세요'),element('p','subtext','파일·업체·현장을 선택하면 연결된 자료와 원문 근거가 여기에 표시됩니다. 선을 선택하면 그 연결의 근거를 볼 수 있습니다.'));const ex=element('div','examples');for(const[id,title,desc]of [['S038','한신건기 두 사진','추정 연결 · 이어지는 문서인지 검토'],['S033','태영 거래명세서 사본','확인된 연결 · ZIP 안팎의 같은 PDF'],['S009','대영산업 갑지와 상세','확인된 연결 · 시트 사이 수식 참조']]){const b=button(title,()=>selectNode(id,{local:true}));b.append(element('small','',desc));ex.append(b);}pane.append(ex);const s=section('확인과 추정의 차이');s.append(element('p','subtext','실선은 원문 표기·수식·동일 파일 해시 등으로 확인한 연결입니다. 점선은 연속 문서·사본·첨부의 추정 또는 미확정 연결입니다. 연결을 확정하거나 거래를 합치지 않습니다.'));pane.append(s);return;}
    pane.append(element('h2','',n.label),element('p','row-context',kindNames[n.kind]));
    pane.append(relatedItems(n.id));
    if(n.kind==='company'||n.kind==='site')pane.append(element('p','subtext','원문 표기를 기준으로 연결했습니다. 같은 법인·현장인지에 대한 별칭 통합이나 거래 일치 판정은 포함하지 않습니다.'));
    if(n.kind==='file'){
      const actions=element('div','actions');const a=link('원본 보기',sourceHref({source_id:n.id}));a.className='action-link';actions.append(a,button('위치 복사',()=>copyPath(n.sourcePath)));pane.append(actions,element('p','path',n.sourcePath));
      if(n.archiveParent)pane.append(element('p','subtext','ZIP 내부 문서입니다. 원본 ZIP과 내부 경로를 함께 보존했습니다.'));
      if(n.documents?.length){const sec=element('details','document-list');sec.append(element('summary','','파일 안의 문서 '+n.documents.length+'건'));for(const d of n.documents){const p=element('div','evidence');p.append(element('p','quote',d.label),link(d.location||'원문 위치',sourceHref(d)));sec.append(p);}pane.append(sec);}
    }
    if(n.issues?.length){const s=section('기존 검토사항 '+n.issueCount+'건'+(n.issueCount>n.issues.length?' 중 '+n.issues.length+'건':''));for(const issue of n.issues){const p=element('p','issue');p.append(element('strong','',issue.kind+' · '),document.createTextNode(issue.text));if(issue.location)p.append(element('span','location',' ['+issue.location+']'));s.append(p);}pane.append(s);}
  }
  async function copyPath(path){try{await navigator.clipboard.writeText(path);toast('원본 위치를 복사했습니다.');}catch{toast('아래 원본 경로를 선택해 복사해 주세요.');}}
  function toast(msg){$('toast').textContent=msg;$('toast').hidden=false;setTimeout(()=>$('toast').hidden=true,2500);}
  function render(){renderList();renderGraph();renderInspector();}
  $('total-count').textContent=data.counts.tables == null ? data.counts.files+'개 파일' : data.counts.tables+'개';
  $('search').addEventListener('input',ev=>{state.query=ev.target.value;state.local=false;$('local').setAttribute('aria-pressed','false');render();fit();});
  document.querySelectorAll('[data-kind]').forEach(b=>b.addEventListener('click',()=>{state.kind=b.dataset.kind;document.querySelectorAll('[data-kind]').forEach(x=>{x.classList.toggle('active',x===b);x.setAttribute('aria-pressed',String(x===b));});renderList();}));
  $('status-filter').addEventListener('change',ev=>{state.status=ev.target.value;render();fit();});
  $('fit').addEventListener('click',()=>{state.local=false;state.query='';state.status='all';state.node=null;state.edge=null;$('search').value='';$('status-filter').value='all';$('local').disabled=true;$('local').setAttribute('aria-pressed','false');render();fit();saveSelection();document.dispatchEvent(new CustomEvent('axis:graph-selection',{detail:{node:state.node,edge:state.edge}}));});
  $('clear-filter').addEventListener('click',()=>$('fit').click());
  $('local').addEventListener('click',()=>{state.local=!state.local;$('local').setAttribute('aria-pressed',String(state.local));render();fit();});
  $('back').addEventListener('click',()=>{const previous=state.history.pop();if(!previous)return;Object.assign(state,previous);$('back').disabled=!state.history.length;$('local').disabled=!state.node;$('local').setAttribute('aria-pressed',String(state.local));render();fit();saveSelection();document.dispatchEvent(new CustomEvent('axis:graph-selection',{detail:{node:state.node,edge:state.edge}}));});
  $('zoom-in').addEventListener('click',()=>window.graph3D?.zoom(1.3));$('zoom-out').addEventListener('click',()=>window.graph3D?.zoom(1/1.3));
  $('mobile-list').addEventListener('click',()=>{$('mobile-list').setAttribute('aria-expanded',String(document.body.classList.toggle('list-open')));});
  const initial=new URLSearchParams(location.hash.slice(1));render();fit();if(initial.get('node'))selectNode(initial.get('node'),{noHistory:true,local:true});else if(initial.get('edge'))selectEdge(initial.get('edge'),{noHistory:true});
  window.graphView={selectNode,selectEdge,state,nodes,edges,fit,describeEdge,refresh:render};
})();
