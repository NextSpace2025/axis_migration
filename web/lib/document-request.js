import {MAX_FILES, MAX_CHARACTERS, PASSAGE_LENGTH} from './document-limits.js';

export const stop=(status,message)=>{throw Object.assign(new Error(message),{httpStatus:status});};
export async function readBody(request) {
  const reader=request.body?.getReader();
  if(!reader) stop(400,'문서를 선택하세요.');
  let n=0; const parts=[];
  for(;;) {
    const {value,done}=await reader.read();
    if(done) break;
    if((n+=value.length)>2000000) { await reader.cancel(); stop(413,'전송 가능한 본문 크기를 넘었습니다.'); }
    parts.push(value);
  }
  try { return JSON.parse(Buffer.concat(parts).toString()); } catch { stop(400,'요청 내용을 확인하세요.'); }
}
export function checkDocs(docs) {
  if(!Array.isArray(docs)||!docs.length||docs.length>MAX_FILES) stop(400,'파일은 1~5개까지 선택하세요.');
  let chars=0;
  for(const d of docs) {
    if(typeof d?.name!=='string'||d.name.length>255||!/\.(docx|hwpx?)$/i.test(d.name)
      ||!Array.isArray(d.passages)||!d.passages.length) stop(400,'문서 형식을 확인하세요.');
    for(const p of d.passages) {
      if(typeof p?.text!=='string'||!p.text.trim()||p.text.length>PASSAGE_LENGTH||typeof p.location!=='string'||p.location.length>128)
        stop(400,'원문 위치와 내용을 확인하세요.');
      chars+=p.text.length;
    }
  }
  if(chars>MAX_CHARACTERS) stop(413,'전체 본문은 6만 자까지 분석할 수 있습니다.');
  return docs.map(({name,passages})=>({name,passages:passages.map(({location,text})=>({location,text}))}));
}
