'use client';
import {useEffect,useState} from 'react';
import TopicResult from './TopicResult.js';
import {MAX_FILES, MAX_CHARACTERS} from '../../lib/document-limits.js';
import './style.css';

const randomKey=()=>Array.from(crypto.getRandomValues(new Uint8Array(32)),b=>b.toString(16).padStart(2,'0')).join('');
export default function Documents(){
  const [id,setId]=useState(''),[owner,setOwner]=useState(''),[files,setFiles]=useState([]),[topic,setTopic]=useState('');
  const [topics,setTopics]=useState([]),[selected,setSelected]=useState(''),[code,setCode]=useState('');
  const [editable,setEditable]=useState(false),[stored,setStored]=useState(false),[busy,setBusy]=useState(false),[reading,setReading]=useState(false),[message,setMessage]=useState('');
  useEffect(()=>{
    const existing=new URLSearchParams(location.search).get('id');
    const job=existing||'run-'+crypto.randomUUID().replaceAll('-','');
    const token=existing?localStorage.getItem('axis-owner-'+job)||'':randomKey();
    setId(job);setOwner(token);
    if(!existing){setEditable(true);return;}
    setStored(true);
    fetch('/api/documents?id='+encodeURIComponent(job),{headers:{'x-document-owner':token}}).then(async r=>{
      const data=await r.json();if(!r.ok)throw Error(data.error);
      setTopics(data.topics);setSelected(data.topics.at(-1)?.topic||'');setEditable(data.editable);
      if(data.editable)setCode(localStorage.getItem('axis-code-'+job)||'');
    }).catch(e=>setMessage(e.message));
  },[]);
  async function readFiles(list){
    setFiles([]);setMessage('');
    if(list.length>MAX_FILES){setMessage('파일은 최대 5개까지 선택하세요.');return;}
    setReading(true);
    let worker;
    try {
      worker=new Worker(new URL('./extract-worker.js',import.meta.url));
      const rows=[];
      for(const file of list){
        const parsed=await new Promise((resolve,reject)=>{
          const timer=setTimeout(()=>reject(Error('파일 읽기 시간이 초과됐습니다. 파일을 다시 선택하세요.')),30000);
          worker.onmessage=e=>{clearTimeout(timer);resolve(e.data);};
          worker.onerror=()=>{clearTimeout(timer);reject(Error('문서를 읽을 수 없습니다.'));};
          worker.postMessage(file);
        });
        rows.push({name:file.name,...parsed});setFiles([...rows]);
      }
    }catch(e){setMessage(e.message);}finally{worker?.terminate();setReading(false);}
  }
  const docs=files.filter(f=>f.document).map(f=>f.document);
  const count=docs.reduce((s,d)=>s+d.passages.reduce((n,p)=>n+p.text.length,0),0);
  async function submit(e){
    e.preventDefault();if(busy)return;
    setBusy(true);setMessage('');
    try{
      localStorage.setItem('axis-owner-'+id,owner);
      const response=await fetch('/api/documents',{method:'POST',headers:{'content-type':'application/json','x-document-owner':owner},
        body:JSON.stringify({id,topic:topic.trim(),documents:stored?undefined:docs})});
      const data=await response.json();if(!response.ok)throw Error(data.error);
      localStorage.setItem('axis-code-'+id,data.code);
      history.replaceState(null,'','/documents?id='+id);
      setStored(true);setCode(data.code);setSelected(data.topic);
      setTopics(old=>[...old.filter(t=>t.topic!==data.topic),data]);setFiles([]);
    }catch(err){setMessage(err.message);}finally{setBusy(false);}
  }
  const current=topics.find(t=>t.topic===selected);
  return <main className="documents"><nav><a href="/">뷰어 홈</a><a href="/results">조회 번호 입력</a>{(stored||files.length>0)&&<a href="/documents">새 문서 분석</a>}</nav>
    <h1>문서 분석</h1>{code&&<p>다시 열 때 사용할 조회 번호 <strong>{code}</strong></p>}
    {editable&&<form onSubmit={submit}>{!stored&&<><label>분석할 문서<input type="file" multiple accept=".docx,.hwp,.hwpx" disabled={busy||reading}
      onChange={e=>readFiles(Array.from(e.target.files))}/></label><small>DOCX · HWP · HWPX / 최대 5개, 파일당 10MB, 본문 합계 6만 자</small>
      <ul>{files.map((f,i)=><li key={i}>{f.name} · {f.error||f.document.passages.length+'개 원문 구절 추출'}</li>)}</ul>
      {reading&&<p role="status">문서를 읽고 있습니다…</p>}{count>MAX_CHARACTERS&&<p>본문 합계가 6만 자를 넘습니다. 파일 수를 줄여주세요.</p>}
      <p>분석을 시작하면 추출한 본문과 결과가 서버에 저장됩니다. 주제 검색을 위해 본문을 OpenAI에 보내고, 관련 구절로 답변을 만듭니다. 조회 번호를 가진 사람은 결과와 인용문을 볼 수 있습니다.</p></>}
      <label>궁금한 주제<input value={topic} maxLength={500} onChange={e=>setTopic(e.target.value)} placeholder="예: 납기 지연과 관련된 업체와 후속 조치" required/></label>
      <button disabled={busy||reading||!topic.trim()||(!stored&&(!docs.length||count>MAX_CHARACTERS))}>{busy?'분석 중…':'주제 분석하기'}</button></form>}
    {message&&<p role="alert">{message}</p>}
    {!!topics.length&&<label>저장된 주제<select value={selected} onChange={e=>setSelected(e.target.value)}>{topics.map(t=><option key={t.topic}>{t.topic}</option>)}</select></label>}
    {current&&<TopicResult key={selected} result={current.result}/>}</main>;
}
