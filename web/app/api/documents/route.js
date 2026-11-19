import {createHash,createHmac,randomUUID} from 'node:crypto';
import {reserveTopic} from '../../../lib/document-jobs.js';
import {privateHeaders,viewerAccess,resultCookie} from '../../../lib/access.js';
import {stop,readBody,checkDocs} from '../../../lib/document-request.js';
import {query} from '../../../lib/db.js';
import {analyze} from '../../../lib/topic-model.js';

export const dynamic='force-dynamic';
export const maxDuration=180;
const send=(value,status=200,headers={})=>Response.json(value,{status,headers:{...privateHeaders,...headers}});
const jobId=/^run-[a-f0-9]{32}$/;
function owner(request) {
  const value=request.headers.get('x-document-owner')||'';
  return /^[a-f0-9]{64}$/.test(value) ? createHash('sha256').update(value).digest('hex') : '';
}
export async function GET(request) {
  const id=new URL(request.url).searchParams.get('id');
  if(!jobId.test(id)) return send({error:'작업 주소를 확인하세요.'},400);
  try {
    const secret=owner(request);
    const {rows:[job]}=await query('select owner_hash from axis_viewer.document_jobs where dataset=$1',[id]);
    if(!job || (viewerAccess(request)?.dataset!==id && job.owner_hash!==secret)) return send({error:'조회 번호로 결과를 여세요.'},403);
    const {rows}=await query('select topic,result from axis_viewer.document_topics where dataset=$1 and result is not null order by started',[id]);
    return send({topics:rows,editable:job.owner_hash===secret});
  } catch {return send({error:'저장된 결과를 읽을 수 없습니다.'},503);}
}
export async function POST(request) {
  let reservation;
  try {
    if(request.headers.get('origin')!==new URL(request.url).origin || !request.headers.get('content-type')?.startsWith('application/json')) stop(403,'뷰어에서 다시 시도하세요.');
    const secret=owner(request);
    if(!secret) stop(403,'작업을 시작한 브라우저에서 여세요.');
    if(!process.env.OPENAI_API_KEY || (process.env.AXIS_VIEWER_PASSWORD||'').length<16) stop(503,'분석 서비스 설정이 필요합니다.');
    const input=await readBody(request);
    const topic=typeof input?.topic==='string' ? input.topic.trim() : '';
    if(!jobId.test(input?.id)||!topic||topic.length>500) stop(400,'주제를 500자 이내로 입력하세요.');
    const id=input.id, attempt=randomUUID();
    const docs=input.documents ? checkDocs(input.documents) : null;
    const ip=process.env.VERCEL==='1'?request.headers.get('x-vercel-forwarded-for')?.split(',')[0].trim():'local';
    const bucket=createHmac('sha256',process.env.AXIS_VIEWER_PASSWORD).update(ip||'unknown').digest('hex');
    const reserved=await reserveTopic(id, topic, secret, docs, bucket, attempt);
    let result=reserved.result;
    if(!result) {
      reservation=[id,topic,attempt];
      result=await analyze(reserved.docs,topic);
      const saved=await query('update axis_viewer.document_topics set result=$4 where dataset=$1 and topic=$2 and attempt=$3',[...reservation,JSON.stringify(result)]);
      if(!saved.rowCount) stop(409,'최근 분석 결과를 다시 확인하세요.');
      reservation=null;
    }
    return send({topic,result,code:reserved.code},200,{'Set-Cookie':resultCookie(request,id)});
  } catch(error) {
    if(reservation) await query('delete from axis_viewer.document_topics where dataset=$1 and topic=$2 and attempt=$3 and result is null',reservation).catch(()=>{});
    return send({error:error.httpStatus?error.message:'분석을 완료하지 못했습니다. 잠시 후 같은 주제로 다시 시도하세요.'},error.httpStatus||503);
  }
}
