import {MAX_FILE_BYTES, MAX_CHARACTERS, PASSAGE_LENGTH} from './document-limits.js';
import {unzipSync, Inflate} from 'fflate';
import * as CFB from 'cfb';
import {SaxesParser} from 'saxes';

const cap = 16 * 1024 * 1024;
function fail(message) { throw new Error(message); }

function xmlRows(bytes, add, section) {
  const xml = new SaxesParser({xmlns:true});
  let paragraph = 0, row = 0, table = 0, inText = 0;
  const stack = [];
  xml.on('doctype', () => fail('지원하지 않는 XML 선언입니다.'));
  xml.on('opentag', tag => {
    const name = tag.local;
    if (name === 'tbl') { table++; row=0; }
    if (name === 'tr') { row++; stack.push({end:'tr', text:'', at:'표 ' + table + ' · 행 ' + row}); }
    if (name === 'p') stack.push({end:'p', text:'', at:'문단 ' + (++paragraph)});
    if (name === 't') inText++;
    if (stack.length && ['tab','br','lineBreak'].includes(name)) stack.at(-1).text += ' ';
  });
  xml.on('text', value => { if (inText && stack.length) stack.at(-1).text += value; });
  xml.on('closetag', tag => {
    if (tag.local === 't') inText--;
    if (stack.at(-1)?.end !== tag.local) return;
    const item = stack.pop();
    if (stack.at(-1)?.end === 'tr' && item.end === 'p') stack.at(-1).text += item.text + ' | ';
    else add(section + item.at, item.text.replace(/ \| $/, ''));
  });
  xml.write(new TextDecoder().decode(bytes)).close();
}

function hwpRows(bytes, add) {
  if (![0xd0,0xcf,0x11,0xe0,0xa1,0xb1,0x1a,0xe1].every((v,i)=>bytes[i]===v))
    fail('HWP 5.x 파일인지 확인하세요.');
  const doc = CFB.read(bytes,{type:'array'});
  const header = Uint8Array.from(CFB.find(doc,'FileHeader')?.content || []);
  if (header.length<40 || !new TextDecoder().decode(header.slice(0,17)).startsWith('HWP Document File') || header[35] !== 5)
    fail('HWP 5.x 파일만 지원합니다.');
  const flags = new DataView(header.buffer,header.byteOffset,header.byteLength).getUint32(36,true);
  if (flags & 6) fail('암호화 또는 배포용 HWP입니다.');
  let total = 0;
  const sections = doc.FullPaths.filter(p => /\/BodyText\/Section\d+$/.test(p)).sort((a,b)=>a.localeCompare(b,'en',{numeric:true}));
  for (const [index,path] of sections.entries()) {
    let body = Uint8Array.from(CFB.find(doc,path).content);
    if (flags & 1) {
      const parts = [];
      const stream = new Inflate(part => {
        total += part.length;
        if (total > cap) fail('압축 해제 용량이 너무 큽니다.');
        parts.push(part);
      });
      for (let pos=0;pos<body.length;pos+=2048) stream.push(body.subarray(pos,pos+2048),pos+2048>=body.length);
      body = new Uint8Array(parts.reduce((n,p)=>n+p.length,0));
      let offset = 0;
      for (const part of parts) { body.set(part,offset); offset += part.length; }
    }
    const data = new DataView(body.buffer,body.byteOffset,body.byteLength);
    let tableLevel = -1, row = null, para = 0, table = 0;
    for (let pos=0;pos<body.length;) {
      const h = data.getUint32(pos,true); pos += 4;
      const tag = h & 1023, level = (h >>> 10) & 1023;
      let size = h >>> 20;
      if (size === 4095) { size = data.getUint32(pos,true); pos += 4; }
      const end = pos + size;
      if (end > body.length) fail('손상된 HWP 레코드입니다.');
      if (level < tableLevel) { tableLevel = -1; row = null; }
      if (tag === 77) { tableLevel = level; table++; row = null; }
      if (tag === 72 && level === tableLevel && size >= 14) row = data.getUint16(pos+8,true)+1;
      if (tag === 67) {
        let value = '';
        for (let i=pos;i+1<end;i+=2) {
          const c = data.getUint16(i,true);
          if (c >= 32) value += String.fromCharCode(c);
          else if ([1,2,3,4,5,6,7,8,9,11,12,14,15,16,17,18,19,20,21,22,23].includes(c)) { i+=14; value+=' '; }
          else value+=' ';
        }
        add('구역 '+(index+1)+' · '+(row ? '표 '+table+' · 행 '+row+' · ' : '')+'문단 '+(++para),value);
      }
      pos = end;
    }
  }
}

export function extract(name, bytes) {
  if (bytes.length > MAX_FILE_BYTES) fail('파일당 10MB까지 읽을 수 있습니다.');
  const passages = [];
  let length = 0;
  function add(location, raw) {
    const text = raw.replace(/\s+/gu,' ').trim();
    length += text.length;
    if (length > MAX_CHARACTERS) fail('본문이 6만 자를 넘습니다.');
    for(let i=0;i<text.length;i+=PASSAGE_LENGTH) passages.push({location,text:text.slice(i,i+PASSAGE_LENGTH)});
  }
  const ext = name.split('.').pop().toLowerCase();
  if (ext === 'hwp') hwpRows(bytes,add);
  else {
    if (!['docx','hwpx'].includes(ext)) fail('DOCX, HWP, HWPX 파일을 선택하세요.');
    let expanded = 0;
    const files = unzipSync(bytes,{filter:file=>{
      const use = ext==='docx' ? file.name==='word/document.xml' : /^Contents\/section\d+\.xml$/i.test(file.name);
      if (use && (expanded += file.originalSize) > cap) fail('문서 본문 용량이 너무 큽니다.');
      return use;
    }});
    for (const [i,key] of Object.keys(files).sort((a,b)=>a.localeCompare(b,'en',{numeric:true})).entries())
      xmlRows(files[key],add,ext==='hwpx'?'구역 '+(i+1)+' · ':'');
  }
  if (!passages.length) fail('읽을 수 있는 본문이 없습니다. 암호 설정이나 이미지 문서인지 확인하세요.');
  return {name,passages};
}
