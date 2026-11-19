import {isDeepStrictEqual} from 'node:util';
import {transaction} from './db.js';
import {resultCode} from './result-code.js';
import {stop} from './document-request.js';

async function openJob(db, id, secret, docs) {
  let {rows:[job]}=await db.query('select j.*,d.access_code from axis_viewer.document_jobs j join axis_viewer.datasets d on d.id=j.dataset where j.dataset=$1',[id]);
  if(job && job.owner_hash!==secret) stop(403,'작업을 시작한 브라우저에서 여세요.');
  if(job && docs && !isDeepStrictEqual(job.documents,docs))
    stop(409,'이미 저장된 작업입니다. 다른 파일은 새 문서 분석에서 선택하세요.');
  if(!job) {
    if(!docs) stop(404,'파일을 다시 선택하세요.');
    for(let i=0;i<12&&!job;i++) {
      const code=resultCode();
      const created=await db.query(`insert into axis_viewer.datasets(id,label,description,default_table,catalog,graph,access_code)
        values($1,'웹 문서 분석','','__web_topics__','{}','{"nodes":[],"edges":[]}', $2) on conflict do nothing`,[id,code]);
      if(created.rowCount) job={documents:docs,access_code:code};
    }
    if(!job) stop(503,'조회 번호를 발급하지 못했습니다.');
    await db.query('insert into axis_viewer.document_jobs values($1,$2,$3)',[id,secret,JSON.stringify(docs)]);
  }
  return job;
}

async function countAnalysis(db, bucket) {
  for(const [key,limit] of [['global',Number(process.env.AXIS_AI_GLOBAL_LIMIT||100)],[bucket,Number(process.env.AXIS_AI_IP_LIMIT||10)]]) {
    if(!Number.isSafeInteger(limit)||limit<0) stop(503,'분석 한도 설정을 확인하세요.');
    if(!limit) stop(429,'오늘의 분석 한도에 도달했습니다.');
    const used=await db.query(`insert into axis_viewer.document_usage as u values((now() at time zone 'UTC')::date,$1,1)
      on conflict(day,bucket) do update set calls=u.calls+1 where u.calls<$2 returning calls`,[key,limit]);
    if(!used.rowCount) stop(429,'오늘의 분석 한도에 도달했습니다.');
  }
}

export function reserveTopic(id, topic, secret, docs, bucket, attempt) {
  return transaction(async db => {
    await db.query('select pg_advisory_xact_lock(hashtext($1))',[id]);
    const job = await openJob(db, id, secret, docs);
    const {rows:[previous]}=await db.query("select result, started > now()-interval '3 minutes' as busy from axis_viewer.document_topics where dataset=$1 and topic=$2",[id,topic]);
    if(previous?.result) return {result:previous.result,code:job.access_code};
    if(previous?.busy) stop(409,'같은 주제를 분석 중입니다. 잠시 후 다시 확인하세요.');
    await countAnalysis(db, bucket);
    await db.query(`insert into axis_viewer.document_topics values($1,$2,$3,now(),null)
      on conflict(dataset,topic) do update set started=now(),attempt=excluded.attempt`,[id,topic,attempt]);
    return {docs:job.documents,code:job.access_code};
  });
}
