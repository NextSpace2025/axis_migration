import {operatorSession} from '../../lib/access.js';
import {query} from '../../lib/db.js';
import {escape,reply} from '../../lib/replies.js';
import {entryPage} from '../../lib/viewer-shell.js';

export const dynamic='force-dynamic';
const pageSize=25;
const page=(content,status=200)=>reply(entryPage('운영자 작업 내역',content),'text/html; charset=utf-8',{},status);

function resultLink(code) {
  return '<a href="/results?code='+encodeURIComponent(code)+'">결과 열기</a>';
}

async function detail(id, file) {
  const {rows:[job]}=await query(`select d.label,d.access_code,j.documents from axis_viewer.datasets d
    left join axis_viewer.document_jobs j on j.dataset=d.id where d.id=$1 and d.access_code is not null`,[id]);
  if(!job) return page('작업을 찾을 수 없습니다.',404);
  const docs=job.documents;
  let html='<p><a href="/history">전체 내역</a></p><h3>'+escape(job.label)+'</h3><p>조회 번호 '+escape(job.access_code)+' · '+resultLink(job.access_code)+'</p>';
  if(!docs) return page(html+'<p>MCP 자료의 파일과 원문 근거는 결과 화면에서 확인할 수 있습니다.</p>');
  html+='<h3>파일명 · 추출 내용</h3><ul>'+docs.map((doc,i)=>'<li><a href="/history?id='+encodeURIComponent(id)+'&amp;file='+i+'">'+escape(doc.name)+'</a> · '+doc.passages.length+'개 구절</li>').join('')+'</ul>';
  if(file!==null){
    const doc=/^\d+$/.test(file)?docs[Number(file)]:null;
    if(!doc) return page('파일을 찾을 수 없습니다.',404);
    html+='<h3>'+escape(doc.name)+'</h3>'+doc.passages.map(p=>'<blockquote><cite>'+escape(p.location)+'</cite><p>'+escape(p.text)+'</p></blockquote>').join('');
  }
  return page(html);
}

export async function GET(request){
  if(!operatorSession(request)) {
    return page('<p>운영자로 로그인하면 파일명, 추출 본문, 조회 번호를 볼 수 있습니다.</p><a class="text-action" href="/login">운영자 로그인</a>');
  }
  const params=new URL(request.url).searchParams;
  try{
    if(params.has('id')) return await detail(params.get('id'),params.get('file'));
    const n=Number(params.get('page')||0);
    if(!Number.isSafeInteger(n)||n<0||n>1000000) return page('페이지 번호를 확인하세요.',400);
    const {rows}=await query(`select d.id,d.label,d.access_code,
      array(select f->>'name' from jsonb_array_elements(j.documents) f) as files,
      (select max(started) from axis_viewer.document_topics where dataset=d.id) as latest
      from axis_viewer.datasets d left join axis_viewer.document_jobs j on j.dataset=d.id
      where d.access_code is not null order by latest desc nulls last,d.id limit $1 offset $2`,[pageSize+1,n*pageSize]);
    let html=rows.length?'<ol>'+rows.slice(0,pageSize).map(row=>'<li><a href="/history?id='+encodeURIComponent(row.id)+'">'+escape(row.files.length?row.files.join(', '):row.label)+'</a><p>조회 번호 '+escape(row.access_code)+' · '+resultLink(row.access_code)+'</p></li>').join('')+'</ol>':'<p>표시할 작업이 없습니다.</p>';
    if(n) html+='<a href="/history?page='+(n-1)+'">이전 페이지</a> ';
    if(rows.length>pageSize) html+='<a href="/history?page='+(n+1)+'">다음 페이지</a>';
    return page(html+'<form action="/login" method="post"><input type="hidden" name="action" value="logout"><button>로그아웃</button></form>');
  }catch(error){
    console.error('History lookup:',error.code||'configuration');
    return page('작업 내역을 불러올 수 없습니다.',503);
  }
}
