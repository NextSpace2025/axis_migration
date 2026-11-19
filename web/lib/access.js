import {createHash, createHmac, timingSafeEqual} from 'node:crypto';

const digest = value => createHash('sha256').update(value).digest();

const sessionName = 'axis_dataset_view';
const sessionSeconds = 12 * 60 * 60;

function viewerPassword() {
  const password = process.env.AXIS_VIEWER_PASSWORD;
  return password?.length >= 16 ? password : null;
}

function isInternalViewer(request, password) {
  const header = request.headers.get('authorization') || '';
  const credentials = header.startsWith('Basic ') ? Buffer.from(header.slice(6), 'base64') : Buffer.alloc(0);
  return timingSafeEqual(digest(credentials), digest('axis:' + password));
}

function signSession(payload, password) {
  return createHmac('sha256',password).update('axis-dataset-view:'+payload).digest('base64url');
}

export function resultCookie(request, dataset) {
  const password = viewerPassword();
  if (!password) throw new Error('Viewer session configuration missing');
  const payload = Buffer.from(JSON.stringify({dataset,expires:Math.floor(Date.now()/1000)+sessionSeconds})).toString('base64url');
  const secure = new URL(request.url).protocol === 'https:' || process.env.VERCEL === '1';
  return `${sessionName}=${payload}.${signSession(payload,password)}; Path=/; Max-Age=${sessionSeconds}; HttpOnly; SameSite=Lax${secure ? '; Secure' : ''}`;
}

export function viewerAccess(request) {
  const password = viewerPassword();
  if (!password) return null;
  const cookie = (request.headers.get('cookie') || '').split(';').map(part => part.trim())
    .find(part => part.startsWith(sessionName+'='))?.slice(sessionName.length+1);
  if (cookie) {
    const match = /^([a-zA-Z0-9_-]{1,300})\.([a-zA-Z0-9_-]{43})$/.exec(cookie);
    if (match && timingSafeEqual(digest(match[2]),digest(signSession(match[1],password)))) {
      try {
        const session = JSON.parse(Buffer.from(match[1],'base64url').toString('utf8'));
        if (typeof session.dataset === 'string' && /^[a-zA-Z0-9_-]{1,128}$/.test(session.dataset) &&
            Number.isSafeInteger(session.expires) && session.expires > Math.floor(Date.now()/1000)) {
          return {dataset:session.dataset};
        }
      } catch {}
    }
  }
  return isInternalViewer(request,password) ? {dataset:null} : null;
}

export function protect(request) {
  const password = viewerPassword();
  if (!password) {
    return new Response('AXIS_VIEWER_PASSWORD 설정이 필요합니다.', {status:503});
  }
  if (isInternalViewer(request,password)) return null;
  return new Response('뷰어에 로그인하세요.', {
    status:401,
    headers:{'WWW-Authenticate':'Basic realm="AXIS Migration", charset="UTF-8"', 'Cache-Control':'no-store'},
  });
}

const operatorCookieName='axis_operator';
function operatorSignature(expiry,password) {
  const signer=createHmac('sha256',password).update('axis-operator-session:'+expiry);
  if(process.env.AXIS_OPERATOR_PASSWORD) signer.update('\0'+process.env.AXIS_OPERATOR_PASSWORD);
  return signer.digest('base64url');
}

export function operatorLogin(username,password) {
  const configured=process.env.AXIS_OPERATOR_PASSWORD || viewerPassword();
  return !!configured && typeof password==='string' &&
    timingSafeEqual(digest(password),digest(configured)) && username==='axis';
}

export function operatorSession(request) {
  const password=viewerPassword();
  if (!password) return false;
  const token=(request.headers.get('cookie')||'').split(';').map(x=>x.trim())
    .find(x=>x.startsWith(operatorCookieName+'='))?.slice(operatorCookieName.length+1);
  const match=/^(\d{10})\.([\w-]{43})$/.exec(token||'');
  return !!match && Number(match[1])>Date.now()/1000 &&
    timingSafeEqual(digest(match[2]),digest(operatorSignature(match[1],password)));
}

export function operatorCookie(request,clear=false) {
  const expiry=String(Math.floor(Date.now()/1000)+sessionSeconds);
  const value=clear?'':expiry+'.'+operatorSignature(expiry,viewerPassword());
  const secure=new URL(request.url).protocol==='https:' || process.env.VERCEL==='1';
  return operatorCookieName+'='+value+'; Path=/; Max-Age='+(clear?0:sessionSeconds)+
    '; HttpOnly; SameSite=Lax'+(secure?'; Secure':'');
}

export const privateHeaders = {
  'Cache-Control':'private, no-store',
  'X-Content-Type-Options':'nosniff',
  'Cross-Origin-Resource-Policy':'same-origin',
  'Referrer-Policy':'no-referrer',
  'Content-Security-Policy':"default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'",
};
