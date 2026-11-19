import {MAX_FILE_BYTES} from '../../lib/document-limits.js';
import {extract} from '../../lib/document-extract.js';
self.onmessage = async ({data:file}) => {
  try {
    if (file.size > MAX_FILE_BYTES) throw Error('파일당 10MB까지 읽을 수 있습니다.');
    self.postMessage({document:extract(file.name,new Uint8Array(await file.arrayBuffer()))});
  } catch(error) { self.postMessage({error:'파일을 읽지 못했습니다. '+error.message.slice(0,150)}); }
};
