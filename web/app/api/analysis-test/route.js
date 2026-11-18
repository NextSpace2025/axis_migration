import {randomInt} from 'node:crypto';
import {protect, privateHeaders} from '../../../lib/access.js';
import {query} from '../../../lib/db.js';
import {problem} from '../../../lib/replies.js';

export async function POST(request) {
  const denied = protect(request);
  if (denied) return denied;
  if (request.headers.get('content-type') !== 'application/json') {
    return problem('JSON 요청이 필요합니다.',415);
  }

  try {
    const numbers = Array.from({length:6}, () => randomInt(1,101));
    for (let attempt = 0; attempt < 20; attempt++) {
      const code = String(randomInt(1000000)).padStart(6,'0');
      const result = await query(
        `insert into axis_viewer.analysis_tests (code,numbers) values ($1,$2)
         on conflict (code) do nothing returning code`,[code,numbers]);
      if (result.rowCount) {
        return Response.json({code,numbers},{status:201,headers:privateHeaders});
      }
    }
    return problem('조회 코드를 발급할 수 없습니다. 다시 시도해 주세요.',503);
  } catch (error) {
    console.error('Analysis test write:',error.code || 'configuration');
    return problem('테스트 결과를 저장할 수 없습니다.',503);
  }
}
