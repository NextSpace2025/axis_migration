import {entryPage} from '../../lib/viewer-shell.js';
import {createHmac} from 'node:crypto';
import {isIP} from 'node:net';
import {privateHeaders, resultCookie} from '../../lib/access.js';
import {query} from '../../lib/db.js';
import {reply} from '../../lib/replies.js';
import {isResultCode, RESULT_CODE_LENGTH} from '../../lib/result-code.js';

export const dynamic = 'force-dynamic';

export async function GET(request) {
  return openResult(request,new URL(request.url).searchParams.get('code'));
}

export async function POST(request) {
  if (request.headers.get('sec-fetch-site') === 'cross-site' ||
      !request.headers.get('content-type')?.startsWith('application/x-www-form-urlencoded')) {
    return new Response(null,{status:400,headers:privateHeaders});
  }
  const form = await request.formData();
  return openResult(request,form.get('code'));
}

async function openResult(request, code) {
  const valid = isResultCode(code);
  let message = '';
  let status = 200;
  const headers = {};
  if (valid) {
    try {
      const suppliedIP = process.env.VERCEL === '1'
        ? request.headers.get('x-vercel-forwarded-for')?.split(',')[0].trim()
        : null;
      const ip = suppliedIP && isIP(suppliedIP) ? suppliedIP : 'unknown';
      const bucket = createHmac('sha256',process.env.AXIS_VIEWER_PASSWORD).update('result-lookup:'+ip).digest('hex');
      const {rows:[result]} = await query(
        'select * from axis_viewer.open_result_code($1,$2)',[code,bucket]);
      if (result.dataset_id) {
        const query = new URLSearchParams({dataset:result.dataset_id,table:result.landing_table,view:'combined'});
        return new Response(null,{
          status:303,
          headers:{...privateHeaders,Location:result.landing_table === '__web_topics__'
            ? '/documents?id='+encodeURIComponent(result.dataset_id) : '/?'+query,
            'Set-Cookie':resultCookie(request,result.dataset_id)},
        });
      }
      if (result.retry_after) {
        headers['Retry-After'] = String(result.retry_after);
        message = '입력 시도가 많습니다. 잠시 후 다시 시도하세요.';
        status = 429;
      } else {
        message = '해당 번호로 등록된 자료가 없습니다.';
        status = 404;
      }
    } catch (error) {
      console.error('Folder lookup:',error.code || 'configuration');
      message = '자료를 조회할 수 없습니다.';
      status = 503;
    }
  } else if (code) {
    message = '숫자 8자리 조회 번호를 입력하세요.';
    status = 400;
  }
  return reply(entryPage('분석 결과 조회', `<form action="/results" method="post">
      <label for="code">8자리 조회 번호</label>
      <input id="code" name="code" inputmode="numeric" minlength="${RESULT_CODE_LENGTH}"
        maxlength="${RESULT_CODE_LENGTH}" pattern="[0-9]{${RESULT_CODE_LENGTH}}"
        autocomplete="off" value="${valid ? code : ''}" required>
      <button type="submit">자료 열기</button>
    </form>${message ? '<p role="status">'+message+'</p>' : ''}`),
    'text/html; charset=utf-8',headers,status);
}
