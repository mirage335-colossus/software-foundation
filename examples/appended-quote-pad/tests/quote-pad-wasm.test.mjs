import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {pathToFileURL} from 'node:url';
import {connectQuoteProvider,encodeOperands,decodeTotal,PROVIDER_SCHEMA,PROVIDER_NAME,UINT32_MAX} from '../src-web-appended/quote-pad-protocol.mjs';
assert.equal(process.argv.length,6,'usage: node quote-pad-wasm.test.mjs PUBLIC_FACADE ADJUSTMENT_ONE_WASM ADJUSTMENT_TWO_WASM REPORT_JSON');
const {createFoundationServices,ServiceStatus:S}=await import(pathToFileURL(process.argv[2]));
const HEADER=64,GEN=1n,SERVICE=101n,PROVIDER=201n;
const schema=await readFile(new URL('../src-bin-appended/provider-schema.json',import.meta.url));
assert.equal(createHash('sha256').update(schema).digest('hex'),Buffer.from(PROVIDER_SCHEMA).toString('hex'));
const schemaDocument=JSON.parse(schema);assert.equal(schemaDocument.name,PROVIDER_NAME);
assert.equal(schemaDocument.operations['1'].request.bytes,8);assert.equal(schemaDocument.operations['1'].reply.bytes,12);
const u32=n=>{const a=new Uint8Array(4);new DataView(a.buffer).setUint32(0,n,true);return a;};
const u64=n=>{const a=new Uint8Array(8);new DataView(a.buffer).setBigUint64(0,n,true);return a;};
const text=s=>new TextEncoder().encode(s),view=b=>new DataView(b.buffer,b.byteOffset,b.byteLength);
const get32=b=>view(b).getUint32(0,true),get64=b=>view(b).getBigUint64(0,true);
function record(fields){const out=new Uint8Array(fields.reduce((n,[,,b])=>n+8+b.length,0));let at=0;
 for(const [id,type,b]of fields){view(out).setUint16(at,id,true);out[at+2]=type;out[at+3]=1;view(out).setUint32(at+4,b.length,true);out.set(b,at+8);at+=8+b.length;}return out;}
function fields(bytes){const out=new Map();let at=0,prior=0;while(at<bytes.length){assert.ok(bytes.length-at>=8);const d=view(bytes),id=d.getUint16(at,true),n=d.getUint32(at+4,true);assert.ok(id>prior);assert.equal(bytes[at+3],1);assert.ok(n<=bytes.length-at-8);out.set(id,{type:bytes[at+2],bytes:bytes.slice(at+8,at+8+n)});prior=id;at+=8+n;}return out;}
function field(f,id,type){assert.equal(f.get(id)?.type,type);return f.get(id).bytes;}
function envelope({kind=3,sequence=1n,handle=SERVICE,operation=1,status=0,correlation=0n,payload=new Uint8Array(),generation=GEN}){
 const out=new Uint8Array(HEADER+payload.length),d=view(out);d.setUint32(0,out.length,true);d.setUint16(4,1,true);d.setUint32(8,kind,true);d.setBigUint64(16,generation,true);d.setBigUint64(24,sequence,true);d.setBigUint64(32,handle,true);d.setUint32(40,operation,true);d.setUint32(44,payload.length,true);d.setUint32(48,status,true);d.setBigUint64(56,correlation,true);out.set(payload,HEADER);return out;}
function completion(request,payload,status=0){const d=view(request);return envelope({kind:4,sequence:d.getBigUint64(24,true),handle:d.getBigUint64(32,true),operation:d.getUint32(40,true),status,payload});}
const bootstrap=Uint8Array.from(Buffer.from('47684bc0172f088d6805b7d49224f4975308e895f6e47824e51673ddd8b86890','hex'));
const providerSchema=Uint8Array.from(Buffer.from('846fd7a2aa16758db702aa30791730ab6de6635a50ba90234995cb06a7ec93de','hex'));
const context=()=>record([[1,2,u64(GEN)],[2,1,u32(65536)],[3,1,u32(64)],[4,1,u32(65536)],[5,7,bootstrap],[6,1,u32(64)],[7,1,u32(64)],[8,1,u32(1048576)]]);
async function guest(url,options={}){
 let instance,lastSequence=0n,lastResponse=null,invocation=0n,registered=false;const pending=new Set(),acks=[],requests=[];
 function gateway(ptr,n,to,capacity){const raw=new Uint8Array(instance.exports.memory.buffer,ptr,n).slice(),d=view(raw);assert.equal(d.getUint32(0,true),n);assert.equal(d.getUint32(8,true),1);assert.equal(d.getBigUint64(16,true),GEN);
  const sequence=d.getBigUint64(24,true),handle=d.getBigUint64(32,true),operation=d.getUint32(40,true),f=fields(raw.subarray(HEADER));assert.ok(sequence>lastSequence);lastSequence=sequence;requests.push({sequence,handle,operation});let payload=new Uint8Array(),status=0;
  if(handle===0n&&operation===1){assert.equal(new TextDecoder().decode(field(f,1,6)),'foundation.providers');assert.deepEqual(field(f,5,7),providerSchema);
   if(options.discoveryFailure)status=S.unavailable;else payload=record([[1,2,u64(SERVICE)],[2,6,text('foundation.providers')],[3,1,u32(1)],[4,1,u32(0)],[5,7,providerSchema],[6,1,u32(32768)]]);pending.add(sequence);
  }else if(handle===0n&&operation===5){const through=get64(field(f,1,2));assert.deepEqual([...pending],[through]);acks.push(through);if(options.ackFailure&&lastResponse)status=S.internal_error;else pending.delete(through);
  }else if(handle===SERVICE&&operation===1){assert.equal(new TextDecoder().decode(field(f,1,6)),PROVIDER_NAME);assert.equal(get32(field(f,2,1)),1);assert.equal(get32(field(f,3,1)),0);assert.deepEqual(field(f,4,7),PROVIDER_SCHEMA);assert.equal(get32(field(f,5,1)),8);assert.equal(get32(field(f,6,1)),12);assert.equal(registered,false);registered=true;payload=record([[1,2,u64(options.badRegistration?0n:PROVIDER)]]);pending.add(sequence);
  }else if(handle===SERVICE&&operation===2){assert.equal(get64(field(f,1,2)),invocation);assert.equal(get64(field(f,2,2)),PROVIDER);lastResponse={status:get32(field(f,3,1)),payload:field(f,4,7).slice()};assert.ok(lastResponse.status===0||lastResponse.payload.length===0);pending.add(sequence);
  }else assert.fail('unexpected guest gateway operation');
  const reply=envelope({kind:2,sequence,handle,operation,status,payload});assert.ok(reply.length<=capacity);new Uint8Array(instance.exports.memory.buffer,to,reply.length).set(reply);return 0;
 }
 const bytes=await readFile(url);({instance}=await WebAssembly.instantiate(bytes,{'foundation.kernel.v1':{call:gateway}}));const e=instance.exports;assert.equal(e.foundation_app_abi_v1(),65536);
 function invoke(name,bytes){const ptr=e.foundation_app_alloc_v1(bytes.length);assert.ok(ptr);new Uint8Array(e.memory.buffer,ptr,bytes.length).set(bytes);try{return e[name](ptr,bytes.length);}finally{e.foundation_app_free_v1(ptr,bytes.length);}}
 function initialize(){return invoke('foundation_app_init_v1',context());}
 function call(operation,payload,{handle=PROVIDER,kind=3,generation=GEN}={}){lastResponse=null;++invocation;const wire=record([[1,2,u64(handle)],[2,1,u32(operation)],[3,7,payload]]);const appStatus=invoke('foundation_app_dispatch_v1',envelope({kind,generation,sequence:invocation,correlation:invocation,payload:wire}));return {appStatus,response:lastResponse};}
 return {e,initialize,call,invoke,pending,acks,requests,sha256:createHash('sha256').update(bytes).digest('hex'),get registered(){return registered;}};
}
const results=[];
for(const [filename,adjustment]of [['adjustment-one.wasm',1],['adjustment-two.wasm',2]]){
 const url=pathToFileURL(process.argv[adjustment+2]),g=await guest(url);assert.equal(g.initialize(),0);assert.equal(g.registered,true);assert.deepEqual(g.acks,[1n,3n]);assert.equal(g.pending.size,0);let count=0;
 for(const [left,right,total,overflow]of [[20,22,42+adjustment,false],[UINT32_MAX-adjustment,0,UINT32_MAX,false],[UINT32_MAX-adjustment+1,0,0,true],[UINT32_MAX,1,0,true],[0,0,adjustment,false]]){
  const got=g.call(1,encodeOperands(left,right));assert.equal(got.appStatus,0);assert.equal(got.response.status,0);assert.deepEqual({...decodeTotal(got.response.payload)},{total,overflow,calls:++count});assert.equal(g.pending.size,0);
 }
 for(const [operation,payload,status]of [[77,new Uint8Array(),S.unknown_operation],[1,new Uint8Array(7),S.invalid_request]]){const got=g.call(operation,payload);assert.equal(got.appStatus,0);assert.equal(got.response.status,status);assert.equal(got.response.payload.length,0);assert.equal(g.pending.size,0);}
 const next=g.call(1,encodeOperands(7,8));assert.deepEqual({...decodeTotal(next.response.payload)},{total:15+adjustment,overflow:false,calls:++count});
 g.e.foundation_app_shutdown_v1(0);assert.equal(g.e.foundation_app_alloc_v1(8),0);assert.equal(g.e.foundation_app_dispatch_v1(0,0),2);
 // The actual public facade and page protocol run over an explicitly modeled
 // serialized owner adapter. enqueue only queues; portable module dispatch and completion
 // delivery happen after admission returns. This is not the native engine owner.
 const h=await guest(url);assert.equal(h.initialize(),0);const queue=[],ownerAcks=[];let pumping=false;
 const foundation=createFoundationServices({enqueue(bytes,source){assert.equal(pumping,false);queue.push({bytes:bytes.slice(),source});return S.ok;},cancel(){return S.expired;},acknowledge(generation,through){assert.equal(pumping,false);assert.equal(generation,GEN);ownerAcks.push(through);return S.ok;}},{generation:GEN});
 function pump(){const item=queue.shift();assert.ok(item);const d=view(item.bytes),handle=d.getBigUint64(32,true);let payload,status=0;pumping=true;
  try{if(handle===0n){assert.equal(item.source,'module');const f=fields(item.bytes.subarray(HEADER));assert.equal(new TextDecoder().decode(field(f,1,6)),PROVIDER_NAME);assert.deepEqual(field(f,5,7),PROVIDER_SCHEMA);payload=record([[1,2,u64(PROVIDER)],[2,6,text(PROVIDER_NAME)],[3,1,u32(1)],[4,1,u32(0)],[5,7,PROVIDER_SCHEMA],[6,1,u32(12)]]);}else{assert.equal(item.source,'automatic');assert.equal(handle,PROVIDER);const r=h.call(d.getUint32(40,true),item.bytes.slice(HEADER));assert.equal(r.appStatus,0);payload=r.response.payload;status=r.response.status;}}
  finally{pumping=false;}
  assert.equal(foundation.receive(completion(item.bytes,payload,status)),true);
 }
 const opening=connectQuoteProvider(foundation);assert.equal(queue.length,1);pump();const calculate=await opening;assert.equal(foundation.acknowledge(),S.ok);
 const answer=calculate(20,22);assert.equal(queue.length,1);pump();assert.deepEqual({...await answer},{total:42+adjustment,overflow:false,calls:1});assert.equal(foundation.acknowledge(),S.ok);assert.equal(h.pending.size,0);assert.deepEqual(ownerAcks,[1n,2n]);
 await assert.rejects(calculate(-1,0),RangeError);assert.equal(queue.length,0);
 foundation.dispose();await assert.rejects(calculate(0,0),error=>error.status===S.closed);h.e.foundation_app_shutdown_v1(0);
 results.push({filename,adjustment,sha256:g.sha256,checkedValidCalls:count,unknownOperationStatus:9,malformedPayloadStatus:1,facadeActualTotal:42+adjustment,gatewayAcks:g.acks.length,ownerAcks:ownerAcks.length});
}
const first=pathToFileURL(process.argv[3]);
for(const bad of [{badRegistration:true},{discoveryFailure:true}]){const g=await guest(first,bad);assert.equal(g.initialize(),2);assert.equal(g.e.foundation_app_alloc_v1(8),0);assert.equal(g.e.foundation_app_dispatch_v1(0,0),2);}
for(const malformed of [{kind:1},{handle:PROVIDER+1n},{generation:GEN+1n}]){const g=await guest(first);assert.equal(g.initialize(),0);const r=g.call(1,encodeOperands(0,0),malformed);assert.equal(r.appStatus,1);assert.equal(r.response,null);assert.equal(g.e.foundation_app_alloc_v1(8),0);assert.equal(g.e.foundation_app_dispatch_v1(0,0),2);}
const badContext=await guest(first);assert.equal(badContext.invoke('foundation_app_init_v1',new Uint8Array(1)),1);assert.equal(badContext.e.foundation_app_init_v1(0,0),2);assert.equal(badContext.requests.length,0);
const failedAck=await guest(first,{ackFailure:true});assert.equal(failedAck.initialize(),0);assert.equal(failedAck.call(1,encodeOperands(20,22)).appStatus,2);assert.equal(failedAck.e.foundation_app_dispatch_v1(0,0),2);
const report={status:'passed',scope:'actual compiled portable module and SDK helper/lifecycle, actual public facade and page protocol with modeled serialized host adapter; no native owner/engine/browser',results,negativeContexts:7,pending:['eligible public retained base','native interpreter/engine integration','actual ordinary browser','visible frame/native publication ACK clocks','pack/compile/inclusive target qualification']};
await writeFile(process.argv[5],JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
