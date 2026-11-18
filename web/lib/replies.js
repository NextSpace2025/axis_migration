import {privateHeaders} from './access.js';

export function reply(body, type = 'text/html; charset=utf-8', headers = {}, status = 200) {
  return new Response(body, {status,headers:{...privateHeaders, 'Content-Type':type, ...headers}});
}

export function problem(message, status) {
  return Response.json({error:message},{status,headers:privateHeaders});
}

export function escape(value) {
  return String(value ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
