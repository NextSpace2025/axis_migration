import {useEffect,useRef,useState} from 'react';

function Evidence({value}) {
  return <blockquote>{value.quote}<cite>{value.file} · {value.location}</cite></blockquote>;
}
export default function TopicResult({result}) {
  const frame=useRef(null);
  const [active,select]=useState(0);
  useEffect(()=>{
    const listener=e=>{
      if(e.origin===location.origin && e.source===frame.current?.contentWindow && Number.isInteger(e.data?.relation)) select(e.data.relation);
    };
    window.addEventListener('message',listener);
    return ()=>window.removeEventListener('message',listener);
  },[]);
  const edge=result?.relations[active];
  return <>
    <section className="graph-pane graph-panel"><header className="panel-heading"><h2>연결 관계</h2></header>
    {result?.relations.length ? (<iframe ref={frame} title="회전 가능한 주제 관계도" src="/topic-graph.html" onLoad={()=>frame.current.contentWindow.postMessage({relations:result.relations},location.origin)}/>) : <p className="analysis-empty">{result?'이 주제에서 확인된 연결이 없습니다.':'분석을 마치면 주제별 관계도가 표시됩니다.'}</p>}</section>
    <aside className="inspector detail-pane" aria-live="polite"><h2>원문 근거</h2>
    {result?.relations.length ? <><label>관계 선택<select value={active} onChange={e=>select(Number(e.target.value))}>{result.relations.map((r,i)=><option key={i} value={i}>{r.from} → {r.to}</option>)}</select></label>
      {edge&&<section><strong>{edge.status==='observed'?'문서에 명시':'AI 추정'} · {edge.label}</strong><Evidence value={edge.evidence}/></section>}</> : <p className="subtext">관계를 선택하면 원문과 위치를 볼 수 있습니다.</p>}</aside></>;
}
export function TopicSummary({result}) {
  return <>
    <h2>분석 요약</h2>{result.findings.map((f,i)=><details key={i}><summary>{f.text}</summary><Evidence value={f.evidence}/></details>)}
    {!result.findings.length && !result.relations.length && <p>이 주제를 뒷받침하는 원문을 찾지 못했습니다.</p>}
    <h2>DB 구조 제안</h2>{!result.tables.length&&<p>표 구조를 제안할 근거가 부족합니다.</p>}
    {result.tables.map(t=><section key={t.name}><h3>{t.name}</h3><p>{t.reason}</p><p>열 · {t.columns.join(', ')}</p><p>기본키 · {t.primaryKey}</p>
      {t.references.map((r,i)=><p key={i}>외래키 · {r.column} → {r.table}.{r.target}</p>)}
      {t.examples.map((r,i)=><details key={i}><summary>예시 행 · {Object.entries(r.values).map(([k,v])=>k+' = '+v).join(', ')}</summary><Evidence value={r.evidence}/></details>)}
      <details><summary>설계 근거</summary><Evidence value={t.evidence}/></details></section>)}
  </>;
}
