import test from 'node:test';
import assert from 'node:assert/strict';
import {zipSync,strToU8,deflateSync} from 'fflate';
import * as CFB from 'cfb';
import {extract} from '../lib/document-extract.js';
import {verified} from '../lib/topic-model.js';

function xmlFixture(hwpx=false) {
  const xml='<doc><p><r><t>납품 일정 회의</t></r></p><tbl><tr><tc><p><r><t>부품 입고가 다음 주로 밀렸다.</t></r></p></tc></tr></tbl></doc>';
  return zipSync({[hwpx?'Contents/section0.xml':'word/document.xml']:strToU8(xml)});
}
function record(tag,level,value) {
  const header=Buffer.alloc(4);header.writeUInt32LE(tag+(level<<10)+(value.length<<20));
  return Buffer.concat([header,value]);
}
function hwpFixture(flags=1) {
  const file=CFB.utils.cfb_new();
  const header=Buffer.alloc(256);header.write('HWP Document File');header[35]=5;header.writeUInt32LE(flags,36);
  CFB.utils.cfb_add(file,'FileHeader',header);
  const cell=Buffer.alloc(32);cell.writeUInt16LE(2,8);
  const body=Buffer.concat([record(67,1,Buffer.from('납품 일정 회의','utf16le')),record(77,2,Buffer.alloc(24)),
    record(72,2,cell),record(67,4,Buffer.from('부품 입고가 다음 주로 밀렸다.','utf16le'))]);
  CFB.utils.cfb_add(file,'BodyText/Section0',Buffer.from(flags&1?deflateSync(body):body));
  return new Uint8Array(CFB.write(file,{type:'buffer'}));
}
test('all three formats preserve paragraphs and table row locations',()=>{
  for(const [name,bytes,row] of [['a.docx',xmlFixture(),1],['a.hwpx',xmlFixture(true),1],['a.hwp',hwpFixture(),3],['b.hwp',hwpFixture(0),3]]) {
    const {passages}=extract(name,bytes);
    assert.deepEqual(passages.map(p=>p.text),['납품 일정 회의','부품 입고가 다음 주로 밀렸다.']);
    assert.match(passages[1].location,new RegExp('표 1 · 행 '+row));
  }
  assert.throws(()=>extract('a.hwp',hwpFixture(3)),/암호/);
  assert.throws(()=>extract('empty.docx',zipSync({'word/document.xml':strToU8('<doc/>')})),/본문/);
  assert.throws(()=>extract('large.docx',new Uint8Array(10*1024*1024+1)),/10MB/);
});
test('five four-page documents keep the last page of each document',()=>{
  const paragraph='입고 예정일과 실제 납품일을 대조하고 다음 회의에서 조치 결과를 확인한다. '.repeat(28);
  const files=Array.from({length:5},(_,i)=>{
    const pages=Array.from({length:4},(_,j)=>'<w:p><w:r><w:t>'+paragraph+'문서'+i+'쪽'+j+'</w:t></w:r></w:p>');
    const xml='<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'+
      pages.join('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')+'</w:body></w:document>';
    return extract(i+'.docx',zipSync({'word/document.xml':strToU8(xml)}));
  });
  for(const [i,file] of files.entries()) assert.ok(file.passages.at(-1).text.endsWith('문서'+i+'쪽3'));
  const length=files.flatMap(f=>f.passages).reduce((n,p)=>n+p.text.length,0);
  assert.ok(length>20000 && length<60000);
});
test('unmatched quotations, invented values and dangling foreign keys are removed',()=>{
  const passages=new Map([[1,{file:'a.hwp',location:'문단 1',text:'대한 업체 일정'}]]);
  const ev={ref:1,quote:'대한 업체'};
  const raw={findings:[{...ev,text:'업체'},{...ev,quote:'없는 인용',text:'오류'}],
    relations:[{...ev,from:'A',to:'B',label:'관련',status:'candidate'}],
    tables:[{...ev,name:'업체',reason:'업체별 기록',primaryKey:'이름',columns:['이름'],
      references:[{column:'이름',table:'유령',target:'번호'}],
      examples:[{...ev,values:{이름:'대한'}},{...ev,values:{이름:'다른 회사'}}]}]};
  const result=verified(raw,passages);
  assert.equal(result.findings.length,1);assert.equal(result.relations[0].status,'candidate');
  assert.deepEqual(result.tables[0].references,[]);assert.equal(result.tables[0].examples.length,1);
  assert.deepEqual(verified({},passages),{findings:[],relations:[],tables:[]});
});
