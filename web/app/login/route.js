import {operatorCookie,operatorLogin,operatorSession,privateHeaders} from '../../lib/access.js';
import {reply} from '../../lib/replies.js';
import {entryPage} from '../../lib/viewer-shell.js';

export const dynamic='force-dynamic';
function loginPage(invalid=false) {
  const form=`<form action="/login" method="post">
    <label for="username">운영자 아이디</label><input id="username" name="username" value="axis" autocomplete="username" required>
    <label for="password">비밀번호</label><input id="password" type="password" name="password" autocomplete="current-password" required autofocus>
    ${invalid?'<p role="alert">아이디와 비밀번호를 확인해 주세요.</p>':''}
    <button type="submit">로그인</button></form>`;
  return reply(entryPage('운영자 로그인',form),'text/html; charset=utf-8',{},invalid?401:200);
}
function redirect(location,cookie) {
  return new Response(null,{status:303,headers:{...privateHeaders,Location:location,...(cookie?{'Set-Cookie':cookie}:{})}});
}
export function GET(request) {
  if(new URL(request.url).searchParams.has('status')) return Response.json({loggedIn:operatorSession(request)},{headers:privateHeaders});
  return operatorSession(request)?redirect('/history'):loginPage();
}
export async function POST(request) {
  if(request.headers.get('origin')!==new URL(request.url).origin ||
     !request.headers.get('content-type')?.startsWith('application/x-www-form-urlencoded')) {
    return new Response(null,{status:403,headers:privateHeaders});
  }
  const form=await request.formData();
  if(form.get('action')==='logout') return redirect('/',operatorCookie(request,true));
  if(!operatorLogin(form.get('username'),form.get('password'))) return loginPage(true);
  return redirect('/history',operatorCookie(request));
}
