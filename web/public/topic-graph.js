window.addEventListener('message',function receive(e){
  if(e.origin!==location.origin||e.source!==parent||!Array.isArray(e.data?.relations)) return;
  window.removeEventListener('message',receive);
  const relations=e.data.relations;
  const labels=[...new Set(relations.flatMap(r=>[r.from,r.to]))];
  const nodes=labels.map((label,i)=>({id:label,label,kind:'file',x:140*Math.cos(i*2*Math.PI/labels.length),y:140*Math.sin(i*2*Math.PI/labels.length)}));
  const edges=relations.map((r,i)=>({...r,id:String(i)}));
  const state={visibleNodes:nodes,visibleEdges:edges};
  const refresh=()=>document.dispatchEvent(new Event('axis:graph-render'));
  function select(i,node=null){
    state.edge=String(i); state.node=node; refresh();
    parent.postMessage({relation:i},location.origin);
  }
  window.graphView={topicAnalysis:true,nodes:new Map(nodes.map(n=>[n.id,n])),edges:new Map(edges.map(r=>[r.id,r])),state,refresh,
    fit:()=>window.graph3D?.fit(),selectEdge:id=>select(Number(id)),selectNode:id=>select(edges.findIndex(e=>e.from===id||e.to===id),id)};
  const script=document.createElement('script');script.src='/graph3d.js';document.body.append(script);
});
