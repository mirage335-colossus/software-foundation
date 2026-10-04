import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const {readTextFile, executeFileService} = await import(pathToFileURL(process.argv[2]));
const encode = text => new TextEncoder().encode(text).buffer;
const file = text => ({size: encode(text).byteLength, slice: () => ({arrayBuffer: async () => encode(text)})});
assert.equal(await readTextFile(file('a\nb'),3),'a\nb');
// Preserve a leading BOM as content, matching the native host byte path.
assert.equal(await readTextFile(file('\ufefffirst\n'),9),'\ufefffirst\n');
await assert.rejects(readTextFile(file('abcd'),3), /no larger/);
await assert.rejects(readTextFile({size: 0, slice:()=>({arrayBuffer:async()=>encode('abcd')})},3),/exceeds/);
await assert.rejects(readTextFile({size: 1, slice:()=>({arrayBuffer:async()=>new Uint8Array([255]).buffer})},3));
class Element {
  constructor(tag) { this.tag=tag;this.children=[];this.listeners={};this.open=false;this.disabled=false; }
  append(...nodes) { this.children.push(...nodes); }
  setAttribute() {} focus() {} remove() {this.removed=true;}
  addEventListener(name, handler) {(this.listeners[name] ||= []).push(handler);}
  fire(name) {for(const handler of this.listeners[name]||[])handler({preventDefault(){},stopPropagation(){}});}
  showModal() {this.open=true;} close() {this.open=false;this.fire('close');}
  click() {this.clicked=true;this.fire('click');}
}
function environment() {
 const nodes=[],revoked=[],timers=[];
 const document={body:new Element('body'),activeElement:null,createElement(tag){const e=new Element(tag);nodes.push(e);return e;},querySelector(){return null;}};
 document.defaultView={Blob, URL:{createObjectURL(){return 'blob:owned';},revokeObjectURL(url){revoked.push(url);}},setTimeout(fn){timers.push(fn);}};
 return {document,nodes,revoked,timers};
}
const request={id:'7',kind:5,title:'Import',value:'',byteLimit:'32'};
{
 const env=environment(),controller=new AbortController();
 let release;const pending=new Promise(resolve=>release=resolve);
 const result=executeFileService(request,{document:env.document,signal:controller.signal});
 env.nodes.find(n=>n.tag==='input').files=[{size:3,slice:()=>({arrayBuffer:()=>pending})}];
 env.nodes.find(n=>n.tag==='form').fire('submit'); controller.abort();
 assert.equal((await result).status,'cancelled');assert.ok(env.nodes[0].removed);
 release(encode('old'));await pending;await Promise.resolve();
 assert.ok(env.nodes[0].removed,'Late file completion resurrected dialog');
}
{
 const env=environment(),controller=new AbortController();controller.abort();
 assert.equal((await executeFileService(request,{document:env.document,signal:controller.signal})).status,'cancelled');
 assert.equal(env.document.body.children.length,0);
}
{
 const env=environment();const result=executeFileService({...request,kind:6,value:'abc'},{document:env.document});
 env.nodes.find(n=>n.tag==='form').fire('submit');
 assert.equal((await result).status,'success');assert.ok(env.nodes.find(n=>n.tag==='a').clicked);
 assert.equal(env.revoked.length,0);env.timers.forEach(fn=>fn());assert.deepEqual(env.revoked,['blob:owned']);
}
{
 const env=environment();const result=executeFileService(request,{document:env.document});
 env.nodes.find(n=>n.tag==='input').files=[file('line')];env.nodes.find(n=>n.tag==='form').fire('submit');
 assert.equal((await result).value,'line');
}
console.log('Bounded UTF-8 files, withdrawal, late completion and user-triggered download passed');
