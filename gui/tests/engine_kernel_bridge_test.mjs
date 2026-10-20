// These tests exercise the production JavaScript bridge with two real, separate
// tiny Wasm memories. Allocator/dispatcher methods below are explicit JS fakes:
// no C++ ABI, Registry, Module, WebCore/JSC, engine binary or browser is executed.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';

const moduleURL=process.argv[2]?pathToFileURL(resolve(process.argv[2])):new URL('../host/engine_kernel_bridge.mjs',import.meta.url);
const {BRIDGE_VERSION,HEADER_BYTES,RECEIPT_BYTES,MAX_SERVICE,OP,ENGINE,CONTROL,RESULT,HOST,
  BridgeError,copyBytes,encodeRecord,decodeRecord,scalar32,scalar64,jsonBytes,
  createCopiedEndpoint,validateEngineProfile,validateDocumentEngineProfile,validateEditorEngineProfile,decodeEditorEngineFacts,inspectKernelEditorProfile,createEngineKernelBridge}=await import(moduleURL.href);
const U64_MAX=(1n<<64n)-1n;
const workerEpoch=U64_MAX-1n;
const initial={worker:workerEpoch,instance:0n,document:0n,generation:0n};
const documentIdentity={worker:workerEpoch,instance:9007199254740993n,document:9007199254740995n,generation:9007199254740997n};
const serviceSequence=9007199254740999n,deliveryTransfer=9007199254741001n,ackTransfer=9007199254741003n;
const secondIdentity={...documentIdentity,document:documentIdentity.document+2n,generation:documentIdentity.generation+2n};
const auditTransfer=9007199254741011n,retirementTransfer=9007199254741013n;
const terminal=error=>error instanceof BridgeError&&error.terminal===true;
const profile=()=>({schema_version:1,kind:'foundation-copied-engine-v1',target:'browser-wasm32',
  binding:'copied-owner-bridge/direct-worker-v1',pointer_bits:32,pthread:false,shared_memory:false,
  bridge_abi:BRIDGE_VERSION,capabilities:'259',contract_sha256:'1'.repeat(64),build_sha256:'2'.repeat(64),source_recipe_sha256:'3'.repeat(64)});

function tinyInstance(){
  const bytes=new Uint8Array([0,97,115,109,1,0,0,0,5,3,1,0,1,7,10,1,6,109,101,109,111,114,121,2,0]);
  return new WebAssembly.Instance(new WebAssembly.Module(bytes));
}
// Deliberately encode the C header layout independently of the production codec.
function receipt(request,{identity=request.identity,transfer=request.transfer,control=CONTROL.OK,service=0,payload=new Uint8Array()}={}){
  const bytes=new Uint8Array(RECEIPT_BYTES+payload.byteLength),view=new DataView(bytes.buffer);
  bytes.set([70,75,66,49]);view.setUint16(4,1,true);view.setUint16(6,request.kind|0x8000,true);
  view.setUint32(8,bytes.byteLength,true);
  ['worker','instance','document','generation'].forEach((key,i)=>view.setBigUint64(16+8*i,identity[key],true));
  view.setBigUint64(48,transfer,true);view.setUint32(56,request.source,true);
  view.setUint32(64,bytes.byteLength-HEADER_BYTES,true);view.setUint32(72,control,true);view.setUint32(76,service,true);
  bytes.set(payload,RECEIPT_BYTES);return bytes;
}
function serviceEnvelope(kind=1,status=0){
  const bytes=new Uint8Array(status?64:66),view=new DataView(bytes.buffer);
  view.setUint32(0,bytes.byteLength,true);view.setUint16(4,1,true);view.setUint32(8,kind,true);
  view.setBigUint64(16,documentIdentity.generation,true);view.setBigUint64(24,serviceSequence,true);
  view.setBigUint64(32,1n,true);view.setUint32(40,1,true);view.setUint32(44,bytes.byteLength-64,true);view.setUint32(48,status,true);
  if(!status)bytes.set([41,42],64);return bytes;
}
function frozenAckReceipt(status=0,identity=documentIdentity){
  const payload=new Uint8Array(12),view=new DataView(payload.buffer);view.setBigUint64(0,serviceSequence,true);view.setUint32(8,status,true);
  return receipt({kind:OP.PEEK_ACK_RECEIPT,identity,transfer:ackTransfer,source:0},{service:status,payload});
}
function fakeModule(role,handler){
  const instance=tinyInstance(),allocations=[],freed=[],calls=[];let next=128;
  const module={instance,allocations,freed,calls,
    get HEAPU8(){return new Uint8Array(instance.exports.memory.buffer);},
    _malloc(length){module.onAllocate?.(length);const pointer=next;next+=Math.max(length,1)+8;
      while(next>instance.exports.memory.buffer.byteLength)instance.exports.memory.grow(1);
      allocations.push({pointer,length});return pointer;},
    _free(pointer){freed.push(pointer);module.onFree?.(pointer);},
    put(bytes){const pointer=module._malloc(bytes.byteLength);module.HEAPU8.set(bytes,pointer);return pointer;}};
  module[role==='kernel'?'_gui_web_engine_bridge_v1':'_bib_engine_wasm_bridge_v1']=()=>BRIDGE_VERSION;
  module[role==='kernel'?'_gui_web_engine_dispatch_v1':'_bib_engine_wasm_dispatch_v1']=(op,p,n,out,cap)=>{
    const raw=new Uint8Array(module.HEAPU8.subarray(p,p+n));
    const request=decodeRecord(raw,{kind:op,receipt:false,maximum:raw.byteLength});calls.push(request);
    const result=handler?handler({op,request,p,n,out,cap,module}):receipt(request,{payload:request.payload});
    if(typeof result==='number')return result;
    if(!(result instanceof Uint8Array))return result;
    assert.ok(result.byteLength<=cap,'fake dispatcher must honor the supplied output capacity');
    module.HEAPU8.set(result,out);return result.byteLength;
  };
  return module;
}

test('copied operation and status constants match the private C header',async()=>{
  const header=await readFile(new URL('../shared/appended_engine_abi.h',import.meta.url),'utf8');
  for(const [name,value] of Object.entries(OP))assert.match(header,new RegExp(`FOUNDATION_ENGINE_${name}\\s*=\\s*${value}\\b`));
  for(const [name,value] of Object.entries(CONTROL))assert.match(header,new RegExp(`FOUNDATION_ENGINE_${name}\\s*=\\s*${value}\\b`));
  for(const [name,value] of Object.entries(RESULT))assert.match(header,new RegExp(`FOUNDATION_ENGINE_${name}\\s*=\\s*${value}\\b`));
  for(const [name,value] of Object.entries(ENGINE))assert.match(header,new RegExp(`FOUNDATION_RETAINED_ENGINE_${name}\\s*=\\s*${value}\\b`));
  for(const [name,value] of Object.entries(HOST))assert.match(header,new RegExp(`FOUNDATION_RETAINED_ENGINE_HOST_${name}\\s*=\\s*${value}\\b`));
  assert.match(header,/FOUNDATION_ENGINE_HEADER_BYTES UINT32_C\(72\)/);
  assert.match(header,/FOUNDATION_ENGINE_RECEIPT_BYTES UINT32_C\(80\)/);
});
test('document browser profile pins bind the unchanged base, additive extension and canonical source catalog',async()=>{
  const path=name=>new URL('../../'+name,import.meta.url),sha=bytes=>createHash('sha256').update(bytes).digest('hex');
  const contractBytes=await readFile(path('abi/engine/document-v2/contract.json')),contract=JSON.parse(contractBytes),
    catalogBytes=await readFile(path('abi/engine/document-v2/catalog.json')),catalog=JSON.parse(catalogBytes),
    extension=await readFile(path('include/foundation/appended/engine_provider_document_v2.h')),
    base=await readFile(path('include/foundation/appended/engine_provider.h')),
    ack=await readFile(path('abi/engine/document-v2/action-ack.json'));
  assert.equal(sha(base),'a8e89da85d34b29a4d1bc454495791fa604b81e3477e48ce8ca902e4333a9c0d');
  assert.equal(contract.base.sha256,sha(base));assert.equal(contract.extension.sha256,sha(extension));
  for(const physical of [false,true]){
    const value={...profile(),kind:'foundation-copied-engine-document-v2',binding:'copied-owner-bridge/direct-worker-document-v2',
      capabilities:physical?'2003':'1795',contract_sha256:sha(contractBytes),provider_abi_major:1,provider_abi_minor:1,host_abi_major:1,host_abi_minor:0,
      document_profile:catalog.profiles[physical?1:0].name,base_header_sha256:sha(base),extension_header_sha256:sha(extension),
      document_catalog_sha256:sha(catalogBytes),document_schema_sha256:catalog.queries[0].schema_sha256,action_ack_schema_sha256:sha(ack),
      viewport_width:800,viewport_height:600,...(physical?{command_catalog_sha256:catalog.profiles[1].physical_input_catalog_sha256,
        surface_protocol_version:1,surface_capabilities:'8225',mouse_input_version:1,key_mapping_version:1,display_scale:1}:{})};
    assert.equal(Object.keys(value).length,physical?30:24);assert.deepEqual(validateDocumentEngineProfile(value),value);
    assert.throws(()=>validateEngineProfile(value),BridgeError);
  }
});
test('request bytes preserve exact LE u64 identities and distinguish zero startup/normal transfer',()=>{
  const body=new Uint8Array([7,8]),identity={...documentIdentity,worker:U64_MAX};
  const encoded=encodeRecord(OP.SUBMIT,identity,body,{source:2,transfer:deliveryTransfer}),view=new DataView(encoded.buffer);
  assert.deepEqual([...encoded.subarray(0,8)],[70,75,66,49,1,0,OP.SUBMIT,0]);
  for(const [i,key] of ['worker','instance','document','generation'].entries())assert.equal(view.getBigUint64(16+i*8,true),identity[key]);
  assert.equal(view.getBigUint64(48,true),deliveryTransfer);assert.equal(view.getUint32(56,true),2);
  assert.equal(view.getUint32(64,true),2);for(const offset of [12,60,68])assert.equal(view.getUint32(offset,true),0);
  body.fill(0);assert.deepEqual(decodeRecord(encoded,{kind:OP.SUBMIT,receipt:false}).payload,new Uint8Array([7,8]));
  const startup=decodeRecord(encodeRecord(OP.CONFIGURE,initial),{kind:OP.CONFIGURE,receipt:false});
  assert.deepEqual(startup.identity,initial);assert.equal(startup.transfer,0n);
  for(const value of [9007199254740993,-1n,U64_MAX+1n])assert.throws(()=>scalar64(value),BridgeError);
  assert.throws(()=>encodeRecord(OP.SUBMIT,{...initial,worker:0n}),BridgeError);
});
test('record decoder rejects wrong identity/kind, reserved bytes, lengths and status domains',()=>{
  const request=decodeRecord(encodeRecord(OP.SUBMIT,documentIdentity),{receipt:false});
  const valid=receipt(request,{payload:new Uint8Array([9])});
  assert.deepEqual(decodeRecord(valid,{kind:OP.SUBMIT,worker:workerEpoch}).payload,new Uint8Array([9]));
  for(const offset of [0,4,8,12,60,64,68]){const bytes=valid.slice();bytes[offset]^=1;assert.throws(()=>decodeRecord(bytes,{kind:OP.SUBMIT}),terminal);}
  for(const [offset,value] of [[56,3],[72,CONTROL.INTERNAL+1],[76,15]]){
    const bytes=valid.slice();new DataView(bytes.buffer).setUint32(offset,value,true);assert.throws(()=>decodeRecord(bytes),terminal);
  }
  assert.throws(()=>decodeRecord(valid,{kind:OP.CANCEL}),terminal);
  assert.throws(()=>decodeRecord(valid,{worker:1n}),terminal);
  assert.throws(()=>decodeRecord(valid.subarray(0,RECEIPT_BYTES-1)),terminal);
});
test('byte copying handles Buffer and hostile subclasses without aliases or virtual access',()=>{
  class Hostile extends Uint8Array {
    get buffer(){throw Error('virtual buffer');}get byteOffset(){throw Error('virtual offset');}get byteLength(){throw Error('virtual length');}
    slice(){throw Error('virtual slice');}subarray(){throw Error('virtual subarray');}*[Symbol.iterator](){throw Error('virtual iterator');}
  }
  for(const original of [new Hostile([1,2,3]),Buffer.from([1,2,3])]){
    const copied=copyBytes(original);original[0]=99;assert.deepEqual(copied,new Uint8Array([1,2,3]));assert.equal(Object.getPrototypeOf(copied),Uint8Array.prototype);
  }
  if(typeof SharedArrayBuffer!=='undefined')assert.throws(()=>copyBytes(new Uint8Array(new SharedArrayBuffer(8))),BridgeError);
});
test('endpoint requires the actual marker/export surface and rejects shared module memory',()=>{
  assert.throws(()=>createCopiedEndpoint({},'kernel'),/maintenance/);
  const wrong=fakeModule('kernel');wrong._gui_web_engine_bridge_v1=()=>1;assert.throws(()=>createCopiedEndpoint(wrong,'kernel'),terminal);
  if(typeof SharedArrayBuffer!=='undefined'){
    const shared=fakeModule('kernel');Object.defineProperty(shared,'HEAPU8',{get:()=>new Uint8Array(new SharedArrayBuffer(64))});
    assert.throws(()=>createCopiedEndpoint(shared,'kernel'),terminal);assert.equal(shared.allocations.length,0);
  }
});
test('two real distinct memories carry maximum copied service records with fresh views after growth',()=>{
  const source=fakeModule('engine'),target=fakeModule('kernel'),sourceEndpoint=createCopiedEndpoint(source,'engine');
  const targetEndpoint=createCopiedEndpoint(target,'kernel');assert.notEqual(source.instance.exports.memory,target.instance.exports.memory);
  const bytes=encodeRecord(OP.SUBMIT,documentIdentity,new Uint8Array(MAX_SERVICE).fill(7)),pointer=source.put(bytes);
  const owned=sourceEndpoint.read(pointer,bytes.byteLength);
  target.onAllocate=()=>{source.instance.exports.memory.grow(1);target.instance.exports.memory.grow(1);};
  const dispatch=target._gui_web_engine_dispatch_v1;target._gui_web_engine_dispatch_v1=(...args)=>{target.instance.exports.memory.grow(1);return dispatch(...args);};
  const output=targetEndpoint.call(OP.SUBMIT,owned),decoded=decodeRecord(output,{kind:OP.SUBMIT});
  assert.equal(decoded.payload.byteLength,MAX_SERVICE);assert.equal(decoded.payload[0],7);assert.equal(target.freed.length,2);
  source.HEAPU8.fill(0,pointer,pointer+bytes.byteLength);assert.equal(decoded.payload.at(-1),7);
});
test('invalid local spans and malformed allocator pointers poison before dispatch or free',()=>{
  for(const pointer of [-1,1.5,0x100000000,0xffffffff]){
    const module=fakeModule('kernel'),endpoint=createCopiedEndpoint(module,'kernel');module._malloc=()=>pointer;
    assert.throws(()=>endpoint.call(OP.SUBMIT,encodeRecord(OP.SUBMIT,documentIdentity)),terminal);
    assert.equal(endpoint.poisoned,true);assert.equal(module.calls.length,0);assert.equal(module.freed.length,0);
    assert.throws(()=>endpoint.call(OP.SUBMIT,new Uint8Array()),terminal);
  }
  const module=fakeModule('engine'),endpoint=createCopiedEndpoint(module,'engine');
  assert.throws(()=>endpoint.read(0xffffffff,8),terminal);assert.equal(endpoint.poisoned,true);
});
test('reply storage is allocated before dispatch and second allocation refusal has no effects',()=>{
  let effects=0;const module=fakeModule('kernel',({request})=>{++effects;assert.equal(module.allocations[0].length,RECEIPT_BYTES);assert.equal(module.allocations.length,2);return receipt(request);});
  const endpoint=createCopiedEndpoint(module,'kernel');endpoint.call(OP.PUMP_ONE,encodeRecord(OP.PUMP_ONE,documentIdentity),RECEIPT_BYTES);
  assert.equal(effects,1);assert.equal(module.freed.length,2);
  const refused=fakeModule('kernel',()=>{++effects;throw Error('unexpected dispatch');}),other=createCopiedEndpoint(refused,'kernel'),malloc=refused._malloc;
  let allocations=0;refused._malloc=n=>++allocations===2?0:malloc(n);
  assert.throws(()=>other.call(OP.PUMP_ONE,encodeRecord(OP.PUMP_ONE,documentIdentity),RECEIPT_BYTES),error=>error.code===CONTROL.LIMIT);
  assert.equal(effects,1);assert.equal(refused.calls.length,0);assert.equal(refused.freed.length,1);assert.equal(other.poisoned,false);
});
test('overlapping allocations, traps and malformed counts poison without export cleanup',()=>{
  for(const kind of ['overlap','trap','too-large','exception','undefined','promise']){
    const module=fakeModule('kernel'),endpoint=createCopiedEndpoint(module,'kernel');
    if(kind==='overlap')module._malloc=()=>128;
    else module._gui_web_engine_dispatch_v1=()=>{if(kind==='trap')throw Error('trap');return kind==='too-large'?RECEIPT_BYTES+1:kind==='exception'?-4:kind==='promise'?Promise.resolve(80):undefined;};
    assert.throws(()=>endpoint.call(OP.SUBMIT,encodeRecord(OP.SUBMIT,documentIdentity),RECEIPT_BYTES),terminal);
    assert.equal(endpoint.poisoned,true);assert.equal(module.freed.length,0);
  }
});
test('malformed typed reply poisons before any subsequent cleanup export',()=>{
  const module=fakeModule('kernel'),endpoint=createCopiedEndpoint(module,'kernel');module._gui_web_engine_dispatch_v1=()=>RECEIPT_BYTES;
  assert.throws(()=>endpoint.call(OP.PUMP_ONE,encodeRecord(OP.PUMP_ONE,documentIdentity),RECEIPT_BYTES),terminal);
  assert.equal(endpoint.poisoned,true);assert.equal(module.freed.length,0);
});
test('caller validation rejects terminal native state before allocation cleanup',()=>{
  const module=fakeModule('engine'),endpoint=createCopiedEndpoint(module,'engine');
  assert.throws(()=>endpoint.call(ENGINE.ADVANCE,encodeRecord(ENGINE.ADVANCE,documentIdentity),RECEIPT_BYTES,reply=>{
    assert.equal(reply.control,CONTROL.OK);throw new BridgeError('native turn did not leave',{terminal:true});
  }),terminal);
  assert.equal(endpoint.poisoned,true);assert.equal(module.freed.length,0);
});
test('contained transport refusals free validated allocations; allocator/free traps remain terminal',()=>{
  for(const code of [-1,-2,-3]){
    const module=fakeModule('kernel',()=>code),endpoint=createCopiedEndpoint(module,'kernel');
    assert.throws(()=>endpoint.call(OP.SUBMIT,encodeRecord(OP.SUBMIT,documentIdentity)),error=>error.code===code);
    assert.equal(endpoint.poisoned,false);assert.equal(module.freed.length,2);
  }
  for(const kind of ['malloc','free']){
    const module=fakeModule('kernel'),endpoint=createCopiedEndpoint(module,'kernel');
    if(kind==='malloc')module._malloc=()=>{throw Error('allocator trap');};else module.onFree=()=>{throw Error('free trap');};
    assert.throws(()=>endpoint.call(OP.SUBMIT,encodeRecord(OP.SUBMIT,documentIdentity)),terminal);
    assert.equal(endpoint.poisoned,true);assert.equal(module.freed.length,kind==='free'?1:0);
  }
});
test('retained profile strictly requires direct non-pthread wasm32 identity and capabilities',()=>{
  assert.equal(validateEngineProfile(profile()).binding,'copied-owner-bridge/direct-worker-v1');
  for(const patch of [{pthread:true},{shared_memory:true},{pointer_bits:64},{binding:'proxy-to-pthread'},
    {target:'native'},{bridge_abi:0},{capabilities:'258'},{capabilities:'467'},{capabilities:'0259'},
    {capabilities:String(U64_MAX)},{capabilities:String(U64_MAX+1n)},{build_sha256:'X'.repeat(64)},{extra:true}])assert.throws(()=>validateEngineProfile({...profile(),...patch}),BridgeError);
});

function scenario({asyncStartup=false,abandonClosedDocumentOutcomes=false,onTerminalOutcome=null,editorInput=false,onEngineAccess=null,beforeOwnerTask=null}={}){
  const tasks=[],events=[],failures=[],submissions=[];let bridge,current={...initial},depth=0,effects=0,actualAcks=0,delivery=null,ack=null;
  let audit=null,pruned=null,auditsCollected=0,disposed=0;
  const hooks={},timers=new Map();let nextTimer=0;
  const timer={setTimeout(fn){timers.set(++nextTimer,fn);return nextTimer;},clearTimeout(id){timers.delete(id);}};
  const kernelModule=fakeModule('kernel',({op,request})=>{
    events.push(['kernel',op,request.transfer]);
    if(hooks.kernel){const result=hooks.kernel(op,request);if(result!==undefined)return result;}
    switch(op){
      case OP.CONFIGURE:return receipt(request,{payload:jsonBytes({entry:'app://fixture/web/index.html'})});
      case OP.TURN_ENTER:depth++;return receipt(request);
      case OP.TURN_LEAVE:assert.ok(depth>0);depth--;return receipt(request);
      case OP.BEGIN_DOCUMENT:assert.ok(depth>0);current={...(request.identity.document===secondIdentity.document?secondIdentity:documentIdentity)};return receipt(request,{identity:current});
      case OP.BEGIN_RESOURCE_EPOCH:assert.ok(depth>0);current={...(request.identity.document===secondIdentity.document?secondIdentity:documentIdentity),generation:0n};return receipt(request,{identity:current,payload:scalar64(17n)});
      case OP.CLOSE_DOCUMENT:assert.ok(depth>0);current={...current,document:0n,generation:0n};return receipt(request);
      case OP.SUBMIT:assert.ok(depth>0);submissions.push(request.payload);return receipt(request);
      case OP.STAGE_ACK:assert.ok(depth>0);assert.equal(new DataView(request.payload.buffer).getBigUint64(0,true),serviceSequence);
        ack??={payload:new Uint8Array(12),transfer:ackTransfer,applied:false};return receipt(request,{service:ack.applied?0:2});
      case OP.PUMP_ONE:
        assert.equal(depth,0);assert.equal(delivery,null,'pump cannot pass unresolved delivery');
        if(ack){assert.equal(ack.applied,false);++actualAcks;ack.applied=true;const data=new DataView(ack.payload.buffer);data.setBigUint64(0,serviceSequence,true);data.setUint32(8,0,true);}
        else if(submissions.length){++effects;submissions.shift();delivery={payload:serviceEnvelope(4),transfer:deliveryTransfer};}
        return receipt(request);
      case OP.PEEK_ACK_RECEIPT:return ack?.applied?receipt(request,{payload:ack.payload,transfer:ack.transfer}):receipt(request,{control:CONTROL.EMPTY});
      case OP.PEEK_DELIVERY:return delivery?receipt(request,{payload:delivery.payload,transfer:delivery.transfer}):receipt(request,{control:CONTROL.EMPTY});
      case OP.DELIVERY_RESULT:{assert.equal(request.transfer,delivery.transfer);const disposition=new DataView(request.payload.buffer).getUint32(0,true);
        if(disposition===RESULT.ACCEPTED)delivery=null;return receipt(request);}
      case OP.ACK_RECEIPT_RESULT:{assert.equal(request.transfer,ack.transfer);const disposition=new DataView(request.payload.buffer).getUint32(0,true);
        if(disposition===RESULT.ACCEPTED)ack=null;return receipt(request);}
      case OP.PEEK_RETIREMENT_AUDIT:
        if(!audit)return receipt(request,{control:CONTROL.EMPTY});
        if(delivery)delivery=null;
        return receipt(request,{identity:audit.identity,transfer:audit.transfer,payload:audit.payload});
      case OP.RETIREMENT_AUDIT_RESULT:
        assert.ok(audit);assert.deepEqual(request.identity,audit.identity);assert.equal(request.transfer,audit.transfer);
        assert.deepEqual(request.payload,scalar32(RESULT.ABANDONED));
        if(!(audit.payload[0]===70&&audit.payload[1]===75&&audit.payload[2]===66&&audit.payload[3]===49))++actualAcks;
        ++auditsCollected;audit=null;delivery=null;ack=null;submissions.length=0;return receipt(request);
      case OP.PEEK_RETIRED_DOCUMENT:
        return pruned&&!audit&&!delivery&&!ack&&!submissions.length?
          receipt(request,{identity:pruned.identity,transfer:pruned.transfer}):receipt(request,{control:CONTROL.EMPTY});
      case OP.RETIRED_DOCUMENT_RESULT:
        assert.ok(pruned);assert.deepEqual(request.identity,pruned.identity);assert.equal(request.transfer,pruned.transfer);
        assert.deepEqual(request.payload,scalar32(RESULT.ACCEPTED));pruned=null;return receipt(request);
      case OP.CLOSE:return receipt(request);
      default:throw Error('Unexpected fake kernel operation '+op);
    }
  });
  const engineModule=fakeModule('engine',({op,request})=>{
    events.push(['engine',op,request.transfer]);
    if(hooks.engine){const result=hooks.engine(op,request);if(result!==undefined)return result;}
    if(op===ENGINE.DESCRIBE)return hooks.describe?hooks.describe(request):receipt(request,{payload:jsonBytes(profile())});
    if(op===ENGINE.START){
      guardedNative(request,()=>native(asyncStartup?OP.BEGIN_RESOURCE_EPOCH:OP.BEGIN_DOCUMENT,new Uint8Array(),{...documentIdentity,generation:0n}));
      const payload=new Uint8Array(8);new DataView(payload.buffer).setUint32(4,2,true);return receipt(request,{identity:current,payload});
    }
    if(op===ENGINE.CURRENT_DOCUMENT){guardedNative(request,()=>{});return receipt(request,{identity:current,control:current.generation?CONTROL.OK:CONTROL.EMPTY});}
    if(op===ENGINE.ADVANCE){guardedNative(request,()=>{
      if(asyncStartup&&!current.generation){if(!hooks.deferDocument)native(OP.BEGIN_DOCUMENT,new Uint8Array(),current);return;}
      return hooks.advance?.()??native(OP.SUBMIT,serviceEnvelope());
    });return receipt(request,{identity:current});}
    if(op===ENGINE.DELIVER_SERVICES||op===ENGINE.COLLECT_ACK){
      const disposition=guardedNative(request,()=>{
        if(op===ENGINE.DELIVER_SERVICES){assert.deepEqual(request.payload,serviceEnvelope(4));return hooks.deliver?hooks.deliver(request):
          (native(OP.STAGE_ACK,scalar64(serviceSequence)),RESULT.ACCEPTED);}
        assert.equal(request.payload.byteLength,12);const applied=native(OP.STAGE_ACK,scalar64(serviceSequence));assert.equal(applied.service,0);
        return hooks.collectAck?hooks.collectAck(request):RESULT.ACCEPTED;
      });
      return receipt(request,{identity:request.identity,payload:scalar32(disposition)});
    }
    if(op===ENGINE.DISPOSE_RETIRED){
      assert.equal(request.payload.byteLength,0);assert.notDeepEqual(request.identity,current);++disposed;
      const status=guardedNative(request,()=>hooks.dispose?hooks.dispose(request):0),body=new Uint8Array(4);new DataView(body.buffer).setInt32(0,status,true);
      return hooks.disposeReply?hooks.disposeReply(request,body):receipt(request,{payload:body});
    }
    throw Error('Unexpected fake engine operation '+op);
  });
  const kernel=createCopiedEndpoint(kernelModule,'kernel'),engineEndpoint=createCopiedEndpoint(engineModule,'engine',()=>{},editorInput?{editorProfile:editorProfile()}:{});
  const engine=onEngineAccess?Object.create(engineEndpoint,Object.fromEntries(['read','validateSpan','write'].map(name=>[name,{value(...args){onEngineAccess(name);return engineEndpoint[name](...args);}}]))):engineEndpoint;
  function native(op,payload=new Uint8Array(),identity=current,transfer=0n){
    const request=encodeRecord(op,identity,payload,{transfer}),pointer=engineModule.put(request),output=engineModule._malloc(RECEIPT_BYTES+MAX_SERVICE);
    const length=bridge.callback(op,pointer,request.byteLength,output,RECEIPT_BYTES+MAX_SERVICE);
    if(length<0)throw new BridgeError('Fake native callback failed',{terminal:true});
    return decodeRecord(engine.read(output,length),{kind:op,worker:workerEpoch});
  }
  function guardedNative(request,action){
    native(OP.TURN_ENTER,new Uint8Array(),request.identity,request.transfer);
    const result=action();native(OP.TURN_LEAVE,new Uint8Array(),request.identity,request.transfer);return result;
  }
  bridge=createEngineKernelBridge({kernel,engine,workerEpoch,post:task=>tasks.push(task),timer,onFailure:error=>failures.push(error),abandonClosedDocumentOutcomes,onTerminalOutcome,beforeOwnerTask});
  return {bridge,kernelModule,engineModule,kernel,engine,hooks,tasks,events,failures,timers,native,
    configure(){bridge.inspect(profile());return bridge.configure(encodeRecord(OP.CONFIGURE,initial));},
    start(){this.configure();return bridge.start(profile(),{entry:'app://fixture/web/index.html'});},
    step(){assert.ok(tasks.length,'expected scheduled owner task');tasks.shift()();},
    flush(limit=30){let count=0;while(tasks.length){assert.ok(count++<limit,'owner tasks must remain bounded');this.step();}},
    queueAudit(payload,{identity=documentIdentity,transfer=auditTransfer,alreadyAppliedAck=false,committedEffect=false}={}){
      audit={payload:new Uint8Array(payload),identity:{...identity},transfer};if(alreadyAppliedAck)++actualAcks;if(committedEffect)++effects;},
    queuePruned(identity=documentIdentity,transfer=retirementTransfer){pruned={identity:{...identity},transfer};},
    markCurrentClosed(){current={...current,document:0n,generation:0n};},
    navigate(){hooks.advance=()=>{native(OP.CLOSE_DOCUMENT);const result=native(OP.BEGIN_DOCUMENT,new Uint8Array(),{...secondIdentity,generation:0n});hooks.advance=()=>scalar32(0);return result;};return bridge.advance();},
    get effects(){return effects;},get actualAcks(){return actualAcks;},get nativeDepth(){return depth;},get auditsCollected(){return auditsCollected;},get disposed(){return disposed;}};
}
test('bridge starts through trusted native BEGIN from zero instance and retains exact adopted u64 identity',()=>{
  const s=scenario();assert.deepEqual(s.start(),documentIdentity);assert.equal(s.bridge.state,'ready');assert.equal(s.bridge.depth,0);assert.equal(s.nativeDepth,0);
  const begin=s.kernelModule.calls.find(request=>request.kind===OP.BEGIN_DOCUMENT);
  assert.equal(begin.identity.instance,documentIdentity.instance);assert.equal(begin.identity.generation,0n);
  const enters=s.kernelModule.calls.filter(request=>request.kind===OP.TURN_ENTER);assert.equal(enters[0].identity.instance,0n);
  assert.ok(enters.every(request=>request.transfer===0n));s.flush();assert.equal(s.effects,0);
});
test('read-only compiled engine inspection precedes kernel initialization and compares profile fields',()=>{
  const s=scenario();assert.throws(()=>s.bridge.configure(encodeRecord(OP.CONFIGURE,initial)),/inspection/);
  assert.equal(s.kernelModule.calls.length,0);
  const reordered=Object.fromEntries(Object.entries(profile()).reverse());assert.deepEqual(s.bridge.inspect(reordered),profile());
  assert.equal(s.kernelModule.calls.length,0);assert.throws(()=>s.bridge.inspect(profile()),/precede/);
  s.bridge.configure(encodeRecord(OP.CONFIGURE,initial));assert.equal(s.kernelModule.calls.length,1);
  const callback=scenario();callback.hooks.describe=request=>{
    assert.equal(callback.bridge.callback(HOST.WAKE,0,0,0,0),-4);return receipt(request,{payload:jsonBytes(profile())});
  };
  assert.throws(()=>callback.bridge.inspect(profile()),terminal);assert.equal(callback.bridge.state,'failed');assert.equal(callback.kernelModule.calls.length,0);
});
test('asynchronous document readiness advances after one START and resolves the native generation',async()=>{
  const s=scenario({asyncStartup:true});assert.deepEqual(s.start(),{...documentIdentity,generation:0n});assert.equal(s.bridge.state,'starting');
  let settled=false;const ready=s.bridge.ready.then(value=>{settled=true;return value;});await Promise.resolve();assert.equal(settled,false);
  assert.equal(s.effects,0);s.step();assert.deepEqual(await ready,documentIdentity);assert.equal(s.bridge.state,'ready');
  assert.equal(s.engineModule.calls.filter(request=>request.kind===ENGINE.START).length,1);
  assert.equal(s.kernelModule.calls.filter(request=>request.kind===OP.BEGIN_RESOURCE_EPOCH).length,1);
  assert.equal(s.kernelModule.calls.filter(request=>request.kind===OP.BEGIN_DOCUMENT).length,1);assert.equal(s.timers.size,0);s.flush();
});
test('close and startup timeout reject readiness and prevent late initialization or START replay',async()=>{
  const closed=scenario({asyncStartup:true});closed.start();const rejected=assert.rejects(closed.bridge.ready,/closed/);
  assert.deepEqual(closed.bridge.close(),{graceful:true});await rejected;const count=closed.engineModule.calls.length;closed.flush();assert.equal(closed.engineModule.calls.length,count);
  const timed=scenario({asyncStartup:true});timed.hooks.deferDocument=true;timed.start();const timeout=assert.rejects(timed.bridge.ready,/timed out/);
  assert.equal(timed.timers.size,1);timed.timers.values().next().value();await timeout;assert.equal(timed.bridge.state,'failed');
  const before=timed.engineModule.calls.length;timed.flush();assert.equal(timed.engineModule.calls.length,before);
  assert.equal(timed.engineModule.calls.filter(request=>request.kind===ENGINE.START).length,1);assert.deepEqual(timed.bridge.close(),{graceful:false});
});
test('private owner task gate holds startup ADVANCE while the original watchdog fires',async()=>{
  let action,resolve;const pending=new Promise(yes=>{resolve=yes;});
  const s=scenario({asyncStartup:true,beforeOwnerTask:task=>{action=task;return pending.then(task);}});
  s.hooks.deferDocument=true;s.start();s.step();
  assert.equal(s.engineModule.calls.filter(request=>request.kind===ENGINE.ADVANCE).length,0);
  assert.equal(s.bridge.state,'starting');assert.equal(typeof action,'function');
  const watchdog=s.timers.values().next().value;assert.equal(typeof watchdog,'function');watchdog();
  await assert.rejects(s.bridge.ready,/startup timed out/);assert.equal(s.bridge.state,'failed');
  resolve();await pending;await Promise.resolve();
  assert.equal(s.engineModule.calls.filter(request=>request.kind===ENGINE.ADVANCE).length,0);
  assert.equal(s.failures.length,1);
});
test('private owner task gate preserves close while startup work waits',async()=>{
  let resolve;const pending=new Promise(yes=>{resolve=yes;});
  const s=scenario({asyncStartup:true,beforeOwnerTask:task=>pending.then(task)});
  s.start();s.step();assert.equal(s.engineModule.calls.filter(request=>request.kind===ENGINE.ADVANCE).length,0);
  s.bridge.close();resolve();await pending;await Promise.resolve();
  assert.equal(s.engineModule.calls.filter(request=>request.kind===ENGINE.ADVANCE).length,0);
  await assert.rejects(s.bridge.ready,/closed|closing/i);
});
test('admission, effect pump, completion, actual ACK and receipt use separate serialized owner tasks',()=>{
  const s=scenario();s.start();s.flush();s.events.length=0;s.bridge.advance();assert.equal(s.effects,0);
  assert.equal(s.kernelModule.calls.filter(request=>request.kind===OP.SUBMIT).length,1);
  s.step();assert.equal(s.effects,1);assert.equal(s.events.some(([role,op])=>role==='engine'&&op===ENGINE.DELIVER_SERVICES),false);
  s.step();assert.equal(s.actualAcks,0);assert.ok(s.events.some(([role,op,transfer])=>role==='engine'&&op===ENGINE.DELIVER_SERVICES&&transfer===deliveryTransfer));
  s.step();assert.equal(s.actualAcks,1);assert.equal(s.events.some(([role,op])=>role==='engine'&&op===ENGINE.COLLECT_ACK),false);
  s.step();assert.ok(s.events.some(([role,op,transfer])=>role==='engine'&&op===ENGINE.COLLECT_ACK&&transfer===ackTransfer));
  const enters=s.kernelModule.calls.filter(request=>request.kind===OP.TURN_ENTER);
  assert.ok(enters.some(request=>request.transfer===deliveryTransfer));assert.ok(enters.some(request=>request.transfer===ackTransfer));
  s.flush();assert.equal(s.effects,1);assert.equal(s.actualAcks,1);assert.equal(s.bridge.depth,0);assert.deepEqual(s.failures,[]);
});
test('rejected delivery blocks engine advance and staged ACK until explicit retry without effect replay',()=>{
  const s=scenario();let reject=true;s.hooks.deliver=()=>{s.native(OP.STAGE_ACK,scalar64(serviceSequence));return reject?RESULT.REJECTED:RESULT.ACCEPTED;};
  s.start();s.flush();s.bridge.advance();s.step();s.step();assert.equal(s.effects,1);assert.equal(s.actualAcks,0);
  assert.equal(s.bridge.advance(),false);s.flush();assert.equal(s.actualAcks,0);
  reject=false;s.bridge.retryDelivery();s.flush();assert.equal(s.effects,1);assert.equal(s.actualAcks,1);assert.deepEqual(s.failures,[]);
  assert.equal(s.kernelModule.calls.filter(request=>request.kind===OP.DELIVERY_RESULT&&new DataView(request.payload.buffer).getUint32(0,true)===RESULT.RETRY).length,1);
});
test('rejected ACK receipt retries exact bytes without applying the ACK twice',()=>{
  const s=scenario();let reject=true;const received=[];s.hooks.collectAck=request=>{received.push(request.payload.slice());return reject?RESULT.REJECTED:RESULT.ACCEPTED;};
  s.start();s.flush();s.bridge.advance();s.flush();assert.equal(s.actualAcks,1);assert.equal(received.length,1);assert.equal(s.bridge.advance(),false);
  reject=false;s.bridge.retryAck();s.flush();assert.deepEqual(received,[received[0],received[0]]);assert.equal(s.actualAcks,1);assert.equal(s.effects,1);assert.deepEqual(s.failures,[]);
});
test('kernel owner cannot reenter engine during pump and close cancels queued effects',()=>{
  const s=scenario();s.start();s.flush();s.hooks.kernel=op=>{if(op===OP.PUMP_ONE)assert.throws(()=>s.bridge.advance(),/entry refused/);};
  s.bridge.advance();s.flush();assert.equal(s.effects,1);assert.deepEqual(s.failures,[]);
  const closing=scenario();closing.start();closing.flush();closing.bridge.advance();assert.deepEqual(closing.bridge.close(),{graceful:true});closing.flush();
  assert.equal(closing.effects,0);assert.equal(closing.bridge.state,'closed');assert.equal(closing.bridge.advance(),false);
});
test('trap, incomplete native turn and wrong delivery guard transfer fail closed without later kernel cleanup',()=>{
  for(const kind of ['trap','incomplete','wrong-transfer']){
    const s=scenario();s.start();s.flush();
    s.hooks.advance=()=>{
      if(kind==='trap')throw Error('engine trap');
      if(kind==='incomplete')s.native(OP.TURN_ENTER);
      else s.native(OP.TURN_ENTER,new Uint8Array(),s.bridge.identity,deliveryTransfer);
    };
    const freed=s.engineModule.freed.length;assert.throws(()=>s.bridge.advance(),terminal);assert.equal(s.bridge.state,'failed');assert.equal(s.engineModule.freed.length,freed);
    const before=s.kernelModule.calls.length;s.flush();
    assert.deepEqual(s.bridge.close(),{graceful:false});assert.equal(s.kernelModule.calls.length,before);assert.equal(s.effects,0);assert.equal(s.failures.length,1);
  }
});
test('malformed service disposition fails without completion retirement or automatic effect retry',()=>{
  const s=scenario();s.hooks.deliver=()=>99;s.start();s.flush();s.bridge.advance();s.step();const freed=s.engineModule.freed.length;s.step();
  assert.equal(s.bridge.state,'failed');assert.equal(s.failures.length,1);assert.equal(s.effects,1);
  assert.equal(s.engineModule.freed.length,freed);
  assert.equal(s.kernelModule.calls.filter(request=>request.kind===OP.DELIVERY_RESULT).length,0);
  s.flush();assert.equal(s.effects,1);assert.deepEqual(s.bridge.close(),{graceful:false});
});
test('uncertain pump outcome freezes before peeking or delivering and cannot be replayed by wake',()=>{
  const s=scenario();s.start();s.flush();s.events.length=0;
  s.hooks.kernel=(op,request)=>op===OP.PUMP_ONE?receipt(request,{service:14}):undefined;
  s.bridge.advance();s.step();assert.equal(s.bridge.state,'failed');assert.equal(s.failures.length,1);
  assert.equal(s.events.filter(([role,op])=>role==='kernel'&&[OP.PEEK_ACK_RECEIPT,OP.PEEK_DELIVERY].includes(op)).length,0);
  const count=s.kernelModule.calls.length;assert.equal(s.bridge.callback(HOST.WAKE,0,0,0,0),-4);s.flush();
  assert.equal(s.kernelModule.calls.length,count);assert.deepEqual(s.bridge.close(),{graceful:false});
});
test('profile mismatch and unsolicited native callbacks cannot start or revive a session',()=>{
  const s=scenario();assert.throws(()=>s.bridge.inspect({...profile(),build_sha256:'9'.repeat(64)}),terminal);assert.equal(s.bridge.state,'failed');assert.equal(s.kernelModule.calls.length,0);
  const other=scenario();assert.equal(other.bridge.callback(OP.SUBMIT,0,0,0,RECEIPT_BYTES),-4);assert.equal(other.bridge.state,'failed');assert.equal(other.failures.length,1);
  assert.equal(other.bridge.callback(HOST.WAKE,0,0,0,0),-4);assert.equal(other.tasks.length,0);
});
test('normal ACK collection reads cached native status without reapplying the actual ACK',()=>{
  const s=scenario();s.start();s.flush();s.bridge.advance();s.flush();
  const staged=s.kernelModule.calls.filter(request=>request.kind===OP.STAGE_ACK);
  assert.equal(staged.length,2);assert.ok(staged.every(request=>request.identity.generation===documentIdentity.generation));
  assert.ok(staged.every(request=>new DataView(request.payload.buffer).getBigUint64(0,true)===serviceSequence));
  assert.equal(s.actualAcks,1);assert.equal(s.effects,1);assert.deepEqual(s.failures,[]);
});
test('engine common ServiceStatus is unused and nonzero values poison before cleanup',()=>{
  const s=scenario();s.start();s.flush();s.hooks.engine=(op,request)=>op===ENGINE.ADVANCE?receipt(request,{service:14}):undefined;
  const freed=s.engineModule.freed.length;assert.throws(()=>s.bridge.advance(),terminal);assert.equal(s.bridge.state,'failed');
  assert.equal(s.engineModule.freed.length,freed);assert.equal(s.engine.poisoned,true);assert.equal(s.effects,0);
});
test('default policy does not automatically collect or dispose document outcomes',()=>{
  const s=scenario();s.start();s.flush();s.navigate();s.queueAudit(serviceEnvelope(4,10));s.queuePruned();s.flush();
  assert.equal(s.auditsCollected,0);assert.equal(s.disposed,0);
  assert.equal(s.kernelModule.calls.filter(request=>[OP.PEEK_RETIREMENT_AUDIT,OP.PEEK_RETIRED_DOCUMENT].includes(request.kind)).length,0);
});
test('trusted closed generation audits then disposes old identity on separate owner tasks',()=>{
  const observed=[],s=scenario({abandonClosedDocumentOutcomes:true,onTerminalOutcome:value=>observed.push(value)});
  s.start();s.flush();s.navigate();s.queueAudit(serviceEnvelope(4,10));s.queuePruned();
  s.step();assert.equal(s.auditsCollected,0);assert.equal(observed.length,0);assert.equal(s.disposed,0);
  s.step();assert.equal(s.auditsCollected,1);assert.equal(s.actualAcks,1);assert.equal(observed.length,1);assert.equal(s.disposed,0);
  s.step();assert.equal(s.disposed,0);s.step();assert.equal(s.disposed,1);s.flush();
  assert.deepEqual(s.bridge.identity,secondIdentity);assert.deepEqual(observed[0].identity,documentIdentity);
  assert.deepEqual(observed[0].bytes,serviceEnvelope(4,10));assert.equal(s.effects,0);
  const disposal=s.engineModule.calls.find(request=>request.kind===ENGINE.DISPOSE_RETIRED);
  assert.deepEqual(disposal.identity,documentIdentity);assert.equal(disposal.transfer,retirementTransfer);
  for(const request of s.kernelModule.calls.filter(request=>[OP.RETIREMENT_AUDIT_RESULT,OP.RETIRED_DOCUMENT_RESULT].includes(request.kind)))
    assert.deepEqual(request.identity,documentIdentity);
  assert.equal(s.engineModule.calls.filter(request=>[ENGINE.DELIVER_SERVICES,ENGINE.COLLECT_ACK].includes(request.kind)).length,0);assert.deepEqual(s.failures,[]);
});
test('uncertain retired completion remains exact owned diagnostic data without service effect replay',()=>{
  const observed=[],s=scenario({abandonClosedDocumentOutcomes:true,onTerminalOutcome:value=>{
    observed.push({identity:value.identity,bytes:value.bytes.slice()});value.bytes.fill(0);
  }}),outcome=serviceEnvelope(4,14);
  s.start();s.flush();s.navigate();s.queueAudit(outcome,{committedEffect:true});s.queuePruned();s.flush();
  assert.equal(s.effects,1);assert.equal(s.actualAcks,1);assert.equal(s.auditsCollected,1);assert.equal(s.disposed,1);
  assert.deepEqual(observed[0].bytes,outcome);assert.equal(new DataView(observed[0].bytes.buffer).getUint32(48,true),14);
  assert.equal(outcome[0],64);assert.deepEqual(s.failures,[]);
});
test('delayed frozen old ACK receipt uses its original identity/status and never applies ACK twice',()=>{
  const observed=[],s=scenario({abandonClosedDocumentOutcomes:true,onTerminalOutcome:value=>observed.push(value)}),original=frozenAckReceipt(14);
  s.start();s.flush();s.navigate();s.queueAudit(original,{alreadyAppliedAck:true});s.queuePruned();s.flush();
  assert.equal(original.byteLength,92);assert.deepEqual(observed[0].identity,documentIdentity);assert.deepEqual(observed[0].bytes,original);
  const decoded=decodeRecord(observed[0].bytes,{kind:OP.PEEK_ACK_RECEIPT});assert.equal(decoded.transfer,ackTransfer);assert.equal(decoded.service,14);
  assert.equal(s.actualAcks,1);assert.equal(s.effects,0);assert.equal(s.disposed,1);
  assert.equal(s.kernelModule.calls.filter(request=>request.kind===OP.STAGE_ACK).length,0);assert.deepEqual(s.failures,[]);
});
test('retirement ACK failure retains exact transaction for explicit retry without repeated observation',()=>{
  const observed=[],s=scenario({abandonClosedDocumentOutcomes:true,onTerminalOutcome:value=>observed.push(value)});let reject=true;
  s.hooks.kernel=(op,request)=>op===OP.RETIREMENT_AUDIT_RESULT&&reject?receipt(request,{service:2}):undefined;
  s.start();s.flush();s.navigate();s.queueAudit(serviceEnvelope(4,14),{committedEffect:true});s.queuePruned();s.flush();
  assert.equal(observed.length,1);assert.equal(s.auditsCollected,0);assert.equal(s.disposed,0);assert.equal(s.bridge.advance(),false);
  const attempts=()=>s.kernelModule.calls.filter(request=>request.kind===OP.RETIREMENT_AUDIT_RESULT);
  assert.equal(attempts().length,1);assert.equal(s.bridge.callback(HOST.WAKE,0,0,0,0),0);s.flush();assert.equal(attempts().length,1);
  reject=false;s.bridge.retryTerminalOutcome();assert.throws(()=>s.bridge.retryTerminalOutcome(),/retry/);s.flush();
  assert.equal(attempts().length,2);assert.ok(attempts().every(request=>request.transfer===auditTransfer));
  for(const request of attempts())assert.deepEqual(request.identity,documentIdentity);
  assert.equal(observed.length,1);assert.equal(s.effects,1);assert.equal(s.actualAcks,1);assert.equal(s.auditsCollected,1);assert.equal(s.disposed,1);assert.deepEqual(s.failures,[]);
});
test('authoritative retirement audit replaces a retained JS delivery before any new old-page callback',()=>{
  for(const kind of ['delivery','ack'])for(const explicitRetry of [false,true]){
    const s=scenario({abandonClosedDocumentOutcomes:true});
    const retire=()=>{
      s.native(OP.CLOSE_DOCUMENT);s.native(OP.BEGIN_DOCUMENT,new Uint8Array(),{...secondIdentity,generation:0n});
      s.queueAudit(kind==='delivery'?serviceEnvelope(4):frozenAckReceipt());s.queuePruned();s.hooks.advance=()=>scalar32(0);return RESULT.REJECTED;
    };
    if(kind==='delivery')s.hooks.deliver=retire;else s.hooks.collectAck=retire;
    s.start();s.flush();s.bridge.advance();s.step();s.step();if(kind==='ack'){s.step();s.step();}
    assert.equal(s.bridge.advance(),false);assert.equal(s.auditsCollected,0);
    if(explicitRetry)try{if(kind==='delivery')s.bridge.retryDelivery();else s.bridge.retryAck();}catch(error){assert.ok(error instanceof BridgeError);}
    s.flush();assert.equal(s.auditsCollected,1);assert.equal(s.disposed,1);assert.equal(s.effects,1);assert.equal(s.actualAcks,1);
    assert.equal(s.engineModule.calls.filter(request=>request.kind===ENGINE.DELIVER_SERVICES).length,1);
    assert.equal(s.engineModule.calls.filter(request=>request.kind===ENGINE.COLLECT_ACK).length,kind==='ack'?1:0);assert.deepEqual(s.failures,[]);
  }
});
test('pending active delivery/ACK and a prospective resource context do not authorize disposal',()=>{
  for(const kind of ['prospective-delivery','ack']){
    const s=scenario({abandonClosedDocumentOutcomes:true});
    if(kind==='prospective-delivery')s.hooks.deliver=()=>{
      s.native(OP.BEGIN_RESOURCE_EPOCH,new Uint8Array(),{...secondIdentity,generation:0n});return RESULT.REJECTED;
    };
    else s.hooks.collectAck=()=>RESULT.REJECTED;
    s.start();s.flush();s.bridge.advance();s.flush();s.queuePruned();
    const peeks=s.kernelModule.calls.filter(request=>[OP.PEEK_RETIREMENT_AUDIT,OP.PEEK_RETIRED_DOCUMENT].includes(request.kind)).length;
    assert.equal(s.bridge.callback(HOST.WAKE,0,0,0,0),0);s.flush();assert.equal(s.disposed,0);assert.equal(s.bridge.advance(),false);
    assert.equal(s.kernelModule.calls.filter(request=>[OP.PEEK_RETIREMENT_AUDIT,OP.PEEK_RETIRED_DOCUMENT].includes(request.kind)).length,peeks);
    assert.deepEqual(s.failures,[]);
  }
});
test('retired disposal rejection, malformed authority and traps poison without free or result replay',()=>{
  for(const kind of ['trap','provider-error','wrong-identity','wrong-transfer','malformed-body','common-service']){
    const s=scenario({abandonClosedDocumentOutcomes:true});s.start();s.flush();s.navigate();s.queuePruned();s.step();
    if(kind==='trap')s.hooks.dispose=()=>{throw Error('native disposal trap');};
    else if(kind==='provider-error')s.hooks.dispose=()=>-1;
    else s.hooks.disposeReply=(request,body)=>receipt(request,{payload:kind==='malformed-body'?new Uint8Array():body,
      identity:kind==='wrong-identity'?secondIdentity:request.identity,transfer:kind==='wrong-transfer'?request.transfer+1n:request.transfer,service:kind==='common-service'?14:0});
    const freed=s.engineModule.freed.length;s.step();assert.equal(s.bridge.state,'failed');assert.equal(s.engineModule.freed.length,freed);assert.equal(s.engine.poisoned,true);
    assert.equal(s.kernelModule.calls.filter(request=>request.kind===OP.RETIRED_DOCUMENT_RESULT).length,0);
    const before=s.kernelModule.calls.length;s.flush();assert.deepEqual(s.bridge.close(),{graceful:false});assert.equal(s.kernelModule.calls.length,before);assert.equal(s.disposed,1);assert.equal(s.failures.length,1);
  }
});
test('retirement audit rejects current or mismatched nested identity without old-page delivery',()=>{
  for(const kind of ['current','foreign-instance','nested-generation']){
    const s=scenario({abandonClosedDocumentOutcomes:true});s.start();s.flush();s.navigate();
    if(kind==='current')s.queueAudit(serviceEnvelope(4,10),{identity:secondIdentity});
    else if(kind==='foreign-instance')s.queueAudit(serviceEnvelope(4,10),{identity:{...documentIdentity,instance:documentIdentity.instance+1n}});
    else s.queueAudit(frozenAckReceipt(0,secondIdentity));
    s.step();assert.equal(s.bridge.state,'failed');assert.equal(s.disposed,0);assert.equal(s.auditsCollected,0);assert.equal(s.failures.length,1);
    assert.equal(s.engineModule.calls.filter(request=>[ENGINE.DELIVER_SERVICES,ENGINE.COLLECT_ACK,ENGINE.DISPOSE_RETIRED].includes(request.kind)).length,0);
  }
});
test('prospective resource context uses last ready metadata for retirement mailboxes',()=>{
  const s=scenario({abandonClosedDocumentOutcomes:true});s.start();s.flush();
  s.hooks.kernel=(op,request)=>{
    if([OP.PEEK_RETIREMENT_AUDIT,OP.PEEK_RETIRED_DOCUMENT].includes(op)){
      assert.deepEqual(request.identity,documentIdentity,'prospective identity is not authoritative current/last-ready metadata');
      return receipt(request,{control:CONTROL.EMPTY});
    }
  };
  s.hooks.advance=()=>s.native(OP.BEGIN_RESOURCE_EPOCH,new Uint8Array(),{...secondIdentity,generation:0n});
  assert.equal(s.bridge.advance(),true);s.flush();assert.equal(s.bridge.state,'ready');assert.deepEqual(s.failures,[]);assert.equal(s.disposed,0);
  assert.equal(s.bridge.identity.generation,0n);
});
test('pending close drains only authoritative terminal outcomes/disposal before graceful close',async()=>{
  const observed=[],s=scenario({abandonClosedDocumentOutcomes:true,onTerminalOutcome:value=>observed.push(value)});let closeCount=0;
  s.start();s.flush();s.bridge.advance();const boundary=s.events.length;
  s.hooks.kernel=(op,request)=>{
    if(op===OP.CLOSE&&++closeCount===1){
      s.markCurrentClosed();s.queueAudit(serviceEnvelope(4,10));s.queuePruned();return receipt(request,{service:2});
    }
  };
  assert.deepEqual(s.bridge.close(),{graceful:false,pending:true});assert.equal(s.bridge.state,'closing');assert.equal(s.bridge.advance(),false);
  let settled=false;const closed=s.bridge.closed.then(value=>{settled=true;return value;});await Promise.resolve();assert.equal(settled,false);
  s.flush();assert.deepEqual(await closed,{graceful:true});assert.equal(s.bridge.state,'closed');assert.equal(closeCount,2);
  assert.equal(s.effects,0);assert.equal(s.auditsCollected,1);assert.equal(s.actualAcks,1);assert.equal(s.disposed,1);assert.equal(observed.length,1);
  assert.equal(s.events.slice(boundary).filter(([role,op])=>role==='kernel'&&op===OP.PUMP_ONE).length,0);
  assert.equal(s.events.slice(boundary).filter(([role,op])=>role==='engine'&&op!==ENGINE.DISPOSE_RETIRED).length,0);assert.deepEqual(s.failures,[]);
});
test('close retires committed metadata behind a prospective context and blocked old delivery',async()=>{
  const s=scenario({abandonClosedDocumentOutcomes:true});let closeCount=0;
  s.hooks.deliver=()=>{s.native(OP.BEGIN_RESOURCE_EPOCH,new Uint8Array(),{...secondIdentity,generation:0n});return RESULT.REJECTED;};
  s.start();s.flush();s.bridge.advance();s.flush();assert.equal(s.bridge.identity.generation,0n);assert.equal(s.effects,1);
  s.hooks.kernel=(op,request)=>{
    if(op===OP.CLOSE&&++closeCount===1){s.markCurrentClosed();s.queueAudit(serviceEnvelope(4));s.queuePruned();return receipt(request,{service:2});}
  };
  assert.deepEqual(s.bridge.close(),{graceful:false,pending:true});s.flush();
  assert.equal(s.bridge.state,'closed','pending close must retire last committed metadata rather than prospective generation zero');
  assert.deepEqual(await s.bridge.closed,{graceful:true});assert.equal(s.auditsCollected,1);assert.equal(s.disposed,1);assert.equal(s.effects,1);
  assert.equal(s.engineModule.calls.filter(request=>request.kind===ENGINE.DELIVER_SERVICES).length,1);assert.deepEqual(s.failures,[]);
});

// Editor fixtures below cover only copied framing and owner scheduling. The
// native binary codec owns deep payload/causality validation in its own tests.
const editorSource=async name=>readFile(new URL('../../abi/appended/editor-v1/'+name,import.meta.url));
const editorContractBytes=await editorSource('contract.json'),editorCatalogBytes=await editorSource('catalog.json'),editorSchemaBytes=await editorSource('binary-schema.json');
const editorSha=value=>createHash('sha256').update(value).digest('hex');
const editorProfile=()=>({...profile(),kind:'foundation-copied-engine-editor-v1',binding:'copied-owner-bridge/direct-worker-editor-v1',capabilities:'2035',
  contract_sha256:editorSha(editorContractBytes),provider_abi_major:1,provider_abi_minor:1,host_abi_major:1,host_abi_minor:0,
  editor_profile:'foundation-engine-copied2035-ndv2-editor-v1',base_header_sha256:'a8e89da85d34b29a4d1bc454495791fa604b81e3477e48ce8ca902e4333a9c0d',
  document_header_sha256:'7b047bae4d0072ef156ea94ba637566d563fea3a95d43c4c6314afc919b1d626',
  document_contract_sha256:'aba7800e6aab1898f3614f0b1ac53e59b9f622bf1e9d3a413f50d672a3662298',
  document_catalog_sha256:'6e555d4c3bb71fbc965e1ca49671fab64d744913e18f45b9ba273505e0c6bcf5',
  physical_catalog_sha256:'d244e6a17561b49b937ad25058f2d662f4f86063633b716bdb87d0250796a47b',
  editor_header_sha256:editorHeaderSha,editor_catalog_sha256:editorSha(editorCatalogBytes),editor_schema_sha256:editorSha(editorSchemaBytes),
  document_schema_sha256:'f11fd061350f8d663dbcdec7cf0a063e4fb0ff3564d285076690f58e8a84143d',
  action_ack_schema_sha256:'1eb6c2d4f56acebc1423d9e2b5bf9a1717a99963a5c3f11f4b9d7b0fe33b50f5',viewport_width:800,viewport_height:600,
  surface_protocol_version:2,surface_capabilities:'8255',mouse_input_version:1,key_mapping_version:1,editor_protocol_version:1,display_scale:1,
  editor_query_max_bytes:236,editor_reply_capacity:1048576,editor_command_max_bytes:1048576});
const editorHeaderSha=editorSha(await readFile(new URL('../../abi/appended/engine_editor_protocol.h',import.meta.url)));
function editorPacket(kind,sequence,{identity=documentIdentity,length=kind===2?64:60,revision=71n,outcome=0}={}){
  const bytes=new Uint8Array(length),view=new DataView(bytes.buffer),offset=kind===2?24:16;
  bytes.set([66,73,66,69,68,86,49,0]);view.setUint16(8,kind,true);view.setUint32(12,length,true);
  if(kind===2)view.setBigUint64(16,revision,true);
  ['worker','instance','document','generation'].forEach((key,index)=>view.setBigUint64(offset+8*index,identity[key],true));
  view.setBigUint64(offset+32,sequence,true);if(kind===4)view.setUint32(56,outcome,true);return bytes;
}
function editorWorkBody(kind,sequence,{payload=editorPacket(kind===1?1:kind===2?3:5,sequence),operation=kind===1?4:kind===2?8:9,schema=editorProfile().editor_schema_sha256,capacity=MAX_SERVICE}={}){
  const bytes=new Uint8Array(56+payload.length),view=new DataView(bytes.buffer);view.setUint32(0,kind,true);view.setUint32(4,operation,true);view.setBigUint64(8,sequence,true);
  bytes.set(Buffer.from(schema,'hex'),16);view.setUint32(48,capacity,true);view.setUint32(52,payload.length,true);bytes.set(payload,56);return bytes;
}
function editorProviderReply(request,kind,sequence,{status=0,disposition=1,handled=0,revision=71n,payload=editorPacket(kind===1?2:4,sequence)}={}){
  const query=kind===1,prefix=query?16:24,bytes=new Uint8Array(prefix+payload.length),view=new DataView(bytes.buffer);
  view.setInt32(0,status,true);if(query){view.setUint32(4,payload.length,true);view.setBigUint64(8,revision,true);}
  else{view.setUint32(4,disposition,true);view.setBigUint64(8,sequence,true);view.setUint32(16,payload.length,true);view.setUint32(20,handled,true);}
  bytes.set(payload,prefix);return receipt(request,{payload:bytes});
}
function editorScenario(options={}){
  const s=scenario({editorInput:true,...options}),collected=[];let pending=null,claimed=false,barrier=0,documentBarrier=0;
  s.hooks.describe=request=>receipt(request,{payload:jsonBytes(editorProfile())});
  s.hooks.kernel=(op,request)=>{
    if(op===OP.PEEK_DOCUMENT_WORK)return receipt(request,{control:CONTROL.EMPTY,service:documentBarrier});
    if(op===OP.PEEK_INPUT)return receipt(request,{control:CONTROL.EMPTY});
    if(op===OP.PEEK_EDITOR_WORK)return pending?receipt(request,{identity:pending.identity,transfer:pending.transfer,payload:pending.body}):receipt(request,{control:CONTROL.EMPTY,service:barrier});
    if(op===OP.BEGIN_EDITOR_WORK){
      assert.ok(pending);assert.equal(claimed,false);assert.equal(s.engineModule.allocations.at(-2).length,pending.kind===1?MAX_SERVICE+96:MAX_SERVICE+104);
      assert.deepEqual(request.identity,pending.identity);assert.equal(request.transfer,pending.transfer);assert.equal(request.payload.length,16);
      const view=new DataView(request.payload.buffer);assert.equal(view.getUint32(0,true),pending.kind);assert.equal(view.getUint32(4,true),0);assert.equal(view.getBigUint64(8,true),pending.sequence);claimed=true;return receipt(request);
    }
    if(op===OP.EDITOR_WORK_RESULT){assert.equal(claimed,true);collected.push(request);pending=null;return receipt(request);}
  };
  s.hooks.engine=(op,request)=>{
    if(![ENGINE.QUERY,ENGINE.COMMAND].includes(op))return;
    assert.equal(claimed,true,'complete kernel claim must precede provider export');assert.ok(pending);
    if(s.provider)return s.provider(request,pending);
    s.turn(request);return editorProviderReply(request,pending.kind,pending.sequence);
  };
  s.hooks.advance=()=>0;
  s.turn=request=>{s.native(OP.TURN_ENTER,new Uint8Array(),request.identity,request.transfer);s.native(OP.TURN_LEAVE,new Uint8Array(),request.identity,request.transfer);};
  s.startEditor=()=>{s.bridge.inspect(editorProfile());s.bridge.configure(encodeRecord(OP.CONFIGURE,initial));s.bridge.start(editorProfile(),{});s.flush();};
  s.offer=(kind,sequence=41n,options={})=>{pending={kind,sequence,identity:options.identity??documentIdentity,transfer:51n,body:editorWorkBody(kind,sequence,options)};claimed=false;s.bridge.poll();};
  s.setBarriers=(documentValue,editorValue)=>{documentBarrier=documentValue;barrier=editorValue;};
  s.collected=collected;return s;
}
test('editor2035 has a distinct exact38-field profile and canonical source pins',()=>{
  const value=editorProfile();assert.equal(Object.keys(value).length,38);assert.deepEqual(validateEditorEngineProfile(value),value);
  assert.throws(()=>validateDocumentEngineProfile(value),BridgeError);assert.throws(()=>validateEngineProfile(value),BridgeError);
  let reads=0;const accessor=editorProfile();Object.defineProperty(accessor,'capabilities',{get(){++reads;return '2035';},enumerable:true});
  assert.throws(()=>validateEditorEngineProfile(accessor),BridgeError);assert.equal(reads,0);
  assert.throws(()=>validateEditorEngineProfile({...value,[Symbol('extra')]:true}),BridgeError);
  const hidden=editorProfile();Object.defineProperty(hidden,'capabilities',{value:'2035',enumerable:false});assert.throws(()=>validateEditorEngineProfile(hidden),BridgeError);
  for(const change of [p=>{p.capabilities='2003';},p=>{p.surface_capabilities='8225';},p=>{p.kind='foundation-copied-engine-document-v2';},
    p=>{p.editor_reply_capacity=1048577;},p=>{p.editor_query_max_bytes=237;},p=>{p.editor_protocol_version=2;},p=>{p.display_scale=true;},
    p=>{p.build_sha256='0'.repeat(64);},p=>{p.source_recipe_sha256='0'.repeat(64);},
    ...Object.keys(value).filter(key=>key.endsWith('_sha256')&&!['build_sha256','source_recipe_sha256'].includes(key)).map(key=>p=>{p[key]='9'.repeat(64);})]){
    const other=editorProfile();change(other);assert.throws(()=>validateEditorEngineProfile(other),BridgeError);
  }
});
test('strict owned editor facts reject duplicate decoded keys, JSON overflow, BOM NUL and lone surrogates',()=>{
  const raw=JSON.stringify(editorProfile());assert.deepEqual(decodeEditorEngineFacts(new TextEncoder().encode(' \n'+raw+'\t ')),editorProfile());
  for(const value of [raw.replace('"kind":','"k\\u0069nd":"duplicate","kind":'),raw.replace('"schema_version":1','"schema_version":1e999'),
    raw.replace('"browser-wasm32"','"\\ud800"'),raw.replace('"browser-wasm32"','"\\udc00"'),raw.replace('"browser-wasm32"','"\\u0000"'),
    raw.replace('"browser-wasm32"','"\\ufeff"'),'\ufeff'+raw,raw+'\0',raw+'{}',raw.replace('"pointer_bits":32','"pointer_bits":[]')])
    assert.throws(()=>decodeEditorEngineFacts(new TextEncoder().encode(value)));
  assert.throws(()=>decodeEditorEngineFacts(new Uint8Array([0xc0,0xaf])));
  if(typeof SharedArrayBuffer!=='undefined')assert.throws(()=>decodeEditorEngineFacts(new Uint8Array(new SharedArrayBuffer(64))));
});
test('editor kernel facts use the new getter with fresh owned memory and no exports after a trap',()=>{
  const module=fakeModule('kernel');module._gui_web_engine_editor_describe_v1=(pointer,capacity)=>{assert.equal(capacity,4096);module.instance.exports.memory.grow(1);const bytes=jsonBytes(editorProfile());module.HEAPU8.set(bytes,pointer);return bytes.length;};
  assert.deepEqual(inspectKernelEditorProfile(module,editorProfile()),editorProfile());assert.equal(module.freed.length,1);
  for(const trap of ['getter','memory','offset-heap','short-heap','free']){
    const bad=fakeModule('kernel');bad._gui_web_engine_editor_describe_v1=(pointer)=>{if(trap==='getter')throw Error('facts trap');const bytes=jsonBytes(editorProfile());bad.HEAPU8.set(bytes,pointer);return bytes.length;};
    if(trap==='memory')Object.defineProperty(bad,'HEAPU8',{get(){throw Error('memory trap');}});
    if(trap==='offset-heap'||trap==='short-heap')Object.defineProperty(bad,'HEAPU8',{get(){const buffer=bad.instance.exports.memory.buffer;return trap==='offset-heap'?new Uint8Array(buffer,1):new Uint8Array(buffer,0,4096);}});
    if(trap==='free')bad._free=()=>{throw Error('free trap');};
    assert.throws(()=>inspectKernelEditorProfile(bad,editorProfile()),terminal);assert.equal(bad.freed.length,0);
  }
});
test('all three editor mailbox kinds reserve, claim, enter and leave exactly once before owned RESULT',()=>{
  for(const kind of [1,2,3]){const s=editorScenario();s.startEditor();s.offer(kind);s.flush();assert.equal(s.bridge.state,'ready');assert.equal(s.collected.length,1);
    const result=s.collected[0],view=new DataView(result.payload.buffer);assert.equal(view.getUint32(0,true),kind);assert.equal(view.getBigUint64(8,true),41n);assert.deepEqual(result.identity,documentIdentity);
    const events=s.events.filter(([role,op])=>role==='kernel'&&[OP.BEGIN_EDITOR_WORK,OP.TURN_ENTER,OP.TURN_LEAVE,OP.EDITOR_WORK_RESULT].includes(op));
    assert.deepEqual(events.slice(-4).map(([,op])=>op),[OP.BEGIN_EDITOR_WORK,OP.TURN_ENTER,OP.TURN_LEAVE,OP.EDITOR_WORK_RESULT]);assert.deepEqual(s.failures,[]);
  }
});
test('editor mailbox rejects schema operation capacity sequence and every five-field wire target substitution before claim',()=>{
  for(const options of [{schema:'9'.repeat(64)},{operation:2},{capacity:MAX_SERVICE-1},
    ...['worker','instance','document','generation'].map(key=>({payload:editorPacket(3,41n,{identity:{...documentIdentity,[key]:documentIdentity[key]+1n}})})),
    {payload:editorPacket(3,42n)},{payload:editorPacket(5,41n)}]){
    const s=editorScenario();s.startEditor();s.offer(2,41n,options);s.flush();assert.equal(s.bridge.state,'failed');assert.equal(s.collected.length,0);
    assert.equal(s.kernelModule.calls.some(value=>value.kind===OP.BEGIN_EDITOR_WORK),false);
  }
  const s=editorScenario();s.startEditor();s.offer(1,U64_MAX);s.flush();assert.equal(s.bridge.state,'failed');assert.equal(s.collected.length,0);
});
test('canonical negative editor pre-entry refusal settles once without a turn while unknown requires its full turn',()=>{
  for(const kind of [1,2,3]){const s=editorScenario();s.startEditor();s.provider=(request,work)=>editorProviderReply(request,kind,work.sequence,{status:-5,disposition:0,revision:0n,payload:new Uint8Array()});
    const enter=s.kernelModule.calls.filter(value=>value.kind===OP.TURN_ENTER).length;s.offer(kind);s.flush();assert.equal(s.bridge.state,'ready');assert.equal(s.collected.length,1);
    assert.equal(s.kernelModule.calls.filter(value=>value.kind===OP.TURN_ENTER).length,enter);
  }
});
test('editor unknown returned evidence copies RESULT once then forbids free ACK replay and all further provider exports',()=>{
  for(const mode of ['query','command','canonical-minus8','inner-unknown']){const s=editorScenario();s.startEditor();const kind=mode==='query'?1:2;let freedAtReturn;
    s.provider=(request,work)=>{s.turn(request);freedAtReturn=s.engineModule.freed.length;return editorProviderReply(request,kind,work.sequence,
      mode==='query'?{status:-8,revision:99n,payload:new Uint8Array([9,8,7])}:mode==='canonical-minus8'?{status:-8,disposition:0,payload:new Uint8Array()}:
      mode==='inner-unknown'?{payload:editorPacket(4,work.sequence,{outcome:3})}:{status:0,disposition:2,handled:1,payload:new Uint8Array([6,5,4])});};
    s.offer(kind);s.flush();assert.equal(s.bridge.state,'failed');assert.equal(s.collected.length,1);assert.equal(s.engineModule.freed.length,freedAtReturn);
    const count=s.engineModule.calls.length;s.bridge.poll();s.bridge.advance();s.bridge.callback(HOST.WAKE,0,0,0,0);s.flush();assert.equal(s.engineModule.calls.length,count);
    assert.equal(s.kernelModule.calls.some(value=>value.kind===OP.STAGE_ACK),false);assert.equal(s.collected.length,1);
  }
});
test('editor traps unbalanced turns and malformed returned joins never manufacture RESULT or LEAVE',()=>{
  for(const mode of ['trap','unbalanced','missing-turn','wrong-transfer','wrong-join']){const s=editorScenario();s.startEditor();let freedAtEntry;
    s.provider=(request,work)=>{freedAtEntry=s.engineModule.freed.length;if(mode==='trap')throw Error('provider trap');
      if(mode==='unbalanced')s.native(OP.TURN_ENTER,new Uint8Array(),request.identity,request.transfer);
      else if(mode==='wrong-transfer')s.native(OP.TURN_ENTER,new Uint8Array(),request.identity,request.transfer+1n);
      else if(mode!=='missing-turn')s.turn(request);
      return editorProviderReply(request,2,work.sequence,{payload:editorPacket(4,work.sequence+(mode==='wrong-join'?1n:0n))});};
    const leaves=s.kernelModule.calls.filter(value=>value.kind===OP.TURN_LEAVE).length;s.offer(2);s.flush();assert.equal(s.bridge.state,'failed');assert.equal(s.collected.length,0);assert.equal(s.engineModule.freed.length,freedAtEntry);
    if(mode!=='wrong-join')assert.equal(s.kernelModule.calls.filter(value=>value.kind===OP.TURN_LEAVE).length,leaves);
  }
});
test('editor allocation refusal precedes claim and the new command limit requires explicit profile and checked prefix',()=>{
  const s=editorScenario();s.startEditor();s.engineModule._malloc=()=>0;s.offer(2);s.flush();assert.equal(s.bridge.state,'failed');assert.equal(s.kernelModule.calls.some(value=>value.kind===OP.BEGIN_EDITOR_WORK),false);
  const large=editorPacket(3,41n,{length:MAX_SERVICE}),work=editorWorkBody(2,41n,{payload:large}),provider=work.subarray(0); // Convert work56 to command56: kind becomes operation.
  new DataView(provider.buffer,provider.byteOffset,provider.byteLength).setUint32(0,8,true);new DataView(provider.buffer,provider.byteOffset,provider.byteLength).setUint32(4,0,true);
  assert.throws(()=>encodeRecord(ENGINE.COMMAND,documentIdentity,provider),BridgeError);
  const encoded=encodeRecord(ENGINE.COMMAND,documentIdentity,provider,{editorProfile:editorProfile()});
  const ordinary=createCopiedEndpoint(fakeModule('engine'),'engine');assert.throws(()=>ordinary.call(ENGINE.COMMAND,encoded),BridgeError);
  const valid=editorScenario();valid.startEditor();valid.offer(2,41n,{payload:large});valid.flush();assert.equal(valid.bridge.state,'ready');assert.equal(valid.collected.length,1);
  const bad=provider.slice();bad[16]^=1;assert.throws(()=>encodeRecord(ENGINE.COMMAND,documentIdentity,bad,{editorProfile:editorProfile()}),BridgeError);
});
test('editor and document EMPTY barriers aggregate without preventing the other lane peek or allowing advance',()=>{
  for(const [documentBarrier,editorBarrier]of [[2,0],[0,2]]){const s=editorScenario();s.startEditor();s.setBarriers(documentBarrier,editorBarrier);
    const advances=s.engineModule.calls.filter(value=>value.kind===ENGINE.ADVANCE).length;s.bridge.advance();s.flush();assert.equal(s.bridge.state,'ready');
    assert.equal(s.engineModule.calls.filter(value=>value.kind===ENGINE.ADVANCE).length,advances);assert.ok(s.kernelModule.calls.some(value=>value.kind===OP.PEEK_EDITOR_WORK));
    s.setBarriers(0,0);s.bridge.poll();s.flush();assert.equal(s.engineModule.calls.filter(value=>value.kind===ENGINE.ADVANCE).length,advances+1);
  }
});
test('editor maximum replies copy a full1MiB binary plus40-byte settlement without widening generic service messages',()=>{
  for(const kind of [1,2]){const s=editorScenario();s.startEditor();s.provider=(request,work)=>{s.turn(request);return editorProviderReply(request,kind,work.sequence,{payload:editorPacket(kind===1?2:4,work.sequence,{length:MAX_SERVICE})});};
    s.offer(kind);s.flush();assert.equal(s.bridge.state,'ready');assert.equal(s.collected.length,1);assert.equal(s.collected[0].payload.length,MAX_SERVICE+40);
    assert.throws(()=>encodeRecord(OP.SUBMIT,documentIdentity,s.collected[0].payload),BridgeError);
  }
  const s=editorScenario();s.startEditor();const allocate=s.engineModule._malloc;let attempts=0;s.engineModule._malloc=length=>++attempts===2?0:allocate(length);
  s.offer(2);s.flush();assert.equal(attempts,2);assert.equal(s.bridge.state,'failed');assert.equal(s.kernelModule.calls.some(value=>value.kind===OP.BEGIN_EDITOR_WORK),false);assert.equal(s.collected.length,0);
});

// These independent fake cache slots model the Guard contract, not its C++
// implementation. Actual native cache/backend-entry evidence is a separate gate.
function formPacket(kind,sequence,{identity=documentIdentity,length=kind===2?81:52,outcome=1,code=1,flags=0,readback=0,requestId=0n}={}){
  const bytes=new Uint8Array(length),view=new DataView(bytes.buffer);bytes.set([78,68,86,50]);view.setUint16(4,2,true);view.setUint16(6,kind,true);
  for(const [offset,value]of [[8,identity.instance],[16,identity.generation],[24,identity.document],[32,sequence],[40,requestId]])view.setBigUint64(offset,value,true);
  if(kind===5){bytes[48]=outcome;bytes[49]=code;bytes[50]=flags;bytes[51]=readback;}return bytes;
}
function documentReplayScenario({abandonClosedDocumentOutcomes=false,onEngineAccess=null}={}){
  const s=scenario({editorInput:true,abandonClosedDocumentOutcomes,onEngineAccess}),collected=[];let pending=null,claimed=false;
  let form=null,latestAck=null,retiredAck=null,backendEntries=0,metadataRetirements=0,cacheHits=0,nextTransfer=151n;
  const matches=(record,request)=>record&&assertIdentity(record.request.identity,request.identity)
    &&Buffer.from(record.request.payload).equals(Buffer.from(request.payload));
  const assertIdentity=(a,b)=>['worker','instance','document','generation'].every(key=>a[key]===b[key]);
  s.hooks.describe=request=>receipt(request,{payload:jsonBytes(editorProfile())});
  s.hooks.kernel=(op,request)=>{
    if(op===OP.PEEK_DOCUMENT_WORK)return pending?receipt(request,{identity:pending.identity,transfer:pending.transfer,payload:pending.body}):receipt(request,{control:CONTROL.EMPTY});
    if([OP.PEEK_EDITOR_WORK,OP.PEEK_INPUT].includes(op))return receipt(request,{control:CONTROL.EMPTY});
    if(op===OP.BEGIN_DOCUMENT_WORK){assert.ok(pending);assert.equal(claimed,false);assert.deepEqual(request.identity,pending.identity);assert.equal(request.transfer,pending.transfer);claimed=true;return receipt(request);}
    if(op===OP.DOCUMENT_WORK_RESULT){assert.equal(claimed,true);collected.push(request);pending=null;claimed=false;return receipt(request);}
  };
  s.turn=request=>{s.native(OP.TURN_ENTER,new Uint8Array(),request.identity,request.transfer);s.native(OP.TURN_LEAVE,new Uint8Array(),request.identity,request.transfer);};
  s.hooks.engine=(op,request)=>{
    if(![ENGINE.QUERY,ENGINE.COMMAND].includes(op))return;
    const record=[form,latestAck,retiredAck].find(value=>matches(value,request));
    if(record){
      ++cacheHits;s.onReplay?.(request);return s.replayReply?s.replayReply(request,record.payload.slice()):receipt(request,{payload:record.payload});
    }
    assert.ok(pending,'fake provider must own new work or an exact cached key');assert.equal(claimed,true);const work=pending;
    if(s.provider)return s.provider(request,work);
    if(work.kind===3){
      const original=new DataView(work.payload.buffer).getBigUint64(0,true);
      const originalMatches=record=>record&&assertIdentity(record.request.identity,request.identity)&&record.sequence===original;
      const code=originalMatches(form)?0:originalMatches(retiredAck)?1:2;
      const payload=new Uint8Array(16),view=new DataView(payload.buffer);view.setBigUint64(0,original,true);view.setUint32(8,code,true);
      const body=decodeRecord(editorProviderReply(request,3,work.sequence,{payload}),{maximum:MAX_SERVICE+104}).payload;
      const record={request,payload:body,sequence:original};if(code===0){++metadataRetirements;form=null;retiredAck=record;}latestAck=record;
      return receipt(request,{payload:body});
    }
    ++backendEntries;s.turn(request);
    const payload=work.completion??formPacket(5,work.sequence,{identity:work.identity});
    const body=decodeRecord(editorProviderReply(request,2,work.sequence,{payload,handled:payload[50]&1}),{maximum:MAX_SERVICE+104}).payload;
    form={request,payload:body,sequence:work.sequence};return receipt(request,{payload:body});
  };
  s.hooks.advance=()=>0;
  s.startDocument=()=>{s.bridge.inspect(editorProfile());s.bridge.configure(encodeRecord(OP.CONFIGURE,initial));s.bridge.start(editorProfile(),{});s.flush();};
  s.offer=(kind,sequence,{identity=documentIdentity,original=41n,completion}={})=>{
    const payload=kind===3?scalar64(original):formPacket(2,sequence,{identity});
    const schema=kind===3?editorProfile().action_ack_schema_sha256:editorProfile().document_schema_sha256;
    const body=new Uint8Array(56+payload.length),view=new DataView(body.buffer);view.setUint32(0,kind,true);view.setUint32(4,kind===3?7:6,true);view.setBigUint64(8,sequence,true);
    body.set(Buffer.from(schema,'hex'),16);view.setUint32(48,kind===3?16:MAX_SERVICE,true);view.setUint32(52,payload.length,true);body.set(payload,56);
    const transfer=nextTransfer++;pending={kind,sequence,identity:{...identity},transfer,payload,body,completion};claimed=false;s.bridge.poll();
    return {kind,identity:{...identity},transfer,sequence};
  };
  Object.defineProperties(s,{backendEntries:{get:()=>backendEntries},metadataRetirements:{get:()=>metadataRetirements},cacheHits:{get:()=>cacheHits}});
  s.collected=collected;return s;
}
const countOperations=(s,operations)=>s.kernelModule.calls.filter(request=>operations.includes(request.kind)).length;

test('owned form replay uses a scheduled metadata-only export with exact private bytes and no new collection',async()=>{
  const s=documentReplayScenario();s.startDocument();const selector=s.offer(2,41n);s.flush();
  const turns=countOperations(s,[OP.TURN_ENTER,OP.TURN_LEAVE]),collections=countOperations(s,[OP.BEGIN_DOCUMENT_WORK,OP.DOCUMENT_WORK_RESULT]),exports=s.engineModule.calls.length;
  const pending=s.bridge.replayDocumentCompletion(selector);selector.identity.document=1n;assert.equal(s.engineModule.calls.length,exports);s.flush();
  const result=await pending;assert.equal(result.operation,6);assert.equal(result.sequence,41n);assert.deepEqual(result.identity,documentIdentity);assert.equal(result.status,0);assert.equal(result.disposition,1);
  assert.equal(Object.isFrozen(result),true);assert.equal(Object.isFrozen(result.identity),true);result.bytes.fill(0);
  const repeated=s.bridge.replayDocumentCompletion({...selector,identity:{...documentIdentity}});s.flush();assert.equal((await repeated).bytes[48],1);
  assert.equal(s.backendEntries,1);assert.equal(s.cacheHits,2);assert.equal(s.collected.length,1);
  assert.equal(countOperations(s,[OP.TURN_ENTER,OP.TURN_LEAVE]),turns);assert.equal(countOperations(s,[OP.BEGIN_DOCUMENT_WORK,OP.DOCUMENT_WORK_RESULT]),collections);assert.deepEqual(s.failures,[]);
});

test('known applied form replay retains the full bounded native result and exact handled fact',async()=>{
  const s=documentReplayScenario();s.startDocument();const completion=formPacket(5,41n,{length:MAX_SERVICE,outcome:0,code:0,flags:1,readback:1});
  const selector=s.offer(2,41n,{completion});s.flush();completion.fill(0);
  assert.equal(s.bridge.state,'ready');assert.equal(s.collected.length,1);
  const pending=s.bridge.replayDocumentCompletion(selector);s.flush();const result=await pending;
  assert.equal(result.written,MAX_SERVICE);assert.equal(result.bytes.length,MAX_SERVICE);assert.equal(result.bytes[48],0);assert.equal(result.bytes[50],1);assert.equal(result.handled,1);
  assert.equal(s.backendEntries,1);assert.equal(s.cacheHits,1);assert.equal(s.collected.length,1);
});

test('ACK replay keeps only latest receipt and original code-zero proof while retiring the exact form cache',async()=>{
  const s=documentReplayScenario();s.startDocument();const form=s.offer(2,41n);s.flush();const first=s.offer(3,42n);s.flush();
  await assert.rejects(s.bridge.replayDocumentCompletion(form),/No exact/);
  const already=s.offer(3,43n);s.flush();const stale=s.offer(3,44n,{original:5n});s.flush();
  for(const [selector,code]of [[first,0],[stale,2]]){const pending=s.bridge.replayDocumentCompletion(selector);s.flush();assert.equal(new DataView((await pending).bytes.buffer).getUint32(8,true),code);}
  await assert.rejects(s.bridge.replayDocumentCompletion(already),/No exact/);assert.equal(s.metadataRetirements,1);
  s.offer(2,45n);s.flush();const next=s.offer(3,46n,{original:45n});s.flush();await assert.rejects(s.bridge.replayDocumentCompletion(first),/No exact/);
  const pending=s.bridge.replayDocumentCompletion(next);s.flush();await pending;assert.equal(s.metadataRetirements,2);assert.equal(s.backendEntries,2);assert.equal(s.cacheHits,3);
});

test('replay selectors cannot supply wire data invoke getters or queue concurrent and reentrant attempts',async()=>{
  const s=documentReplayScenario();s.startDocument();const selector=s.offer(2,41n);s.flush();const exports=s.engineModule.calls.length;
  const getter={...selector};Object.defineProperty(getter,'sequence',{enumerable:true,get(){throw Error('must not invoke selector getter');}});
  for(const value of [null,{...selector,payload:new Uint8Array()},{...selector,kind:1},{...selector,sequence:42n},{...selector,transfer:selector.transfer+1n},
    {...selector,identity:{...documentIdentity,worker:1n}},{...selector,identity:{...documentIdentity,extra:0n}},getter])await assert.rejects(s.bridge.replayDocumentCompletion(value),BridgeError);
  assert.equal(s.engineModule.calls.length,exports);
  const pending=s.bridge.replayDocumentCompletion(selector);await assert.rejects(s.bridge.replayDocumentCompletion(selector),/quiescent/);
  let reentrant;s.onReplay=()=>{reentrant=s.bridge.replayDocumentCompletion(selector);};s.flush();await pending;await assert.rejects(reentrant,/quiescent/);assert.equal(s.cacheHits,1);
});

test('known preentry refusals and inner or outer unknown form completions never acquire replay authority',async()=>{
  for(const mode of ['preentry','inner-unknown','outer-unknown']){
    const s=documentReplayScenario();s.startDocument();s.provider=(request,work)=>{
      if(mode!=='preentry')s.turn(request);
      return editorProviderReply(request,2,work.sequence,mode==='preentry'?{status:-1,disposition:0,payload:new Uint8Array()}:
        mode==='outer-unknown'?{status:-8,disposition:2,payload:new Uint8Array([7,6])}:{payload:formPacket(5,work.sequence,{outcome:2})});
    };
    const selector=s.offer(2,41n);s.flush();const exports=s.engineModule.calls.length;
    await assert.rejects(s.bridge.replayDocumentCompletion(selector),BridgeError);assert.equal(s.engineModule.calls.length,exports);assert.equal(s.cacheHits,0);
  }
});

test('inner form unknown preserves one raw collection then forbids free replay and every later interpreter export',async()=>{
  const s=documentReplayScenario();s.startDocument();let freedAtReturn;
  s.provider=(request,work)=>{s.turn(request);const reply=editorProviderReply(request,2,work.sequence,{payload:formPacket(5,work.sequence,{outcome:2})});freedAtReturn=s.engineModule.freed.length;return reply;};
  const selector=s.offer(2,41n);s.flush();assert.equal(s.bridge.state,'failed');assert.equal(s.engine.poisoned,true);
  assert.equal(s.engineModule.freed.length,freedAtReturn);assert.equal(s.collected.length,1);assert.equal(s.collected[0].payload[40+48],2);
  const metadata=new DataView(s.collected[0].payload.buffer);assert.equal(metadata.getInt32(16,true),0);assert.equal(metadata.getUint32(20,true),1);
  const exports=s.engineModule.calls.length;await assert.rejects(s.bridge.replayDocumentCompletion(selector),BridgeError);
  assert.equal(s.bridge.poll(),false);assert.equal(s.bridge.advance(),false);assert.equal(s.bridge.callback(HOST.WAKE,0,0,0,0),-4);s.flush();
  assert.equal(s.engineModule.calls.length,exports);assert.equal(s.engineModule.freed.length,freedAtReturn);assert.equal(s.collected.length,1);
});

test('malformed closed form completion prefixes poison before free collection or another interpreter export',async()=>{
  const cases=[['outcome',{outcome:3}],['code',{code:9}],['flags',{flags:4}],['readback',{readback:2}],
    ['post-effect rejection',{flags:1}],['popup without effects',{outcome:2,flags:2}],['accepted without readback',{outcome:0,code:0}],
    ['accepted nonzero code',{outcome:0,code:1,readback:1,length:53}],['trailing without readback',{length:53}],['unknown invalid code',{outcome:2,code:9}],
    ['rejected handled mismatch',{handled:1}],['applied handled mismatch',{outcome:0,code:0,flags:1,readback:1,length:53,handled:0}]];
  for(const [name,options]of cases){
    const s=documentReplayScenario();s.startDocument();let freedAtReturn;
    s.provider=(request,work)=>{s.turn(request);const reply=editorProviderReply(request,2,work.sequence,{payload:formPacket(5,work.sequence,options),handled:options.handled??((options.flags??0)&1)});freedAtReturn=s.engineModule.freed.length;return reply;};
    const selector=s.offer(2,41n);s.flush();assert.equal(s.bridge.state,'failed',name);assert.equal(s.engine.poisoned,true,name);
    assert.equal(s.engineModule.freed.length,freedAtReturn,name);assert.equal(s.collected.length,0,name);
    const exports=s.engineModule.calls.length;await assert.rejects(s.bridge.replayDocumentCompletion(selector),BridgeError);
    assert.equal(s.bridge.poll(),false);assert.equal(s.bridge.advance(),false);assert.equal(s.bridge.callback(HOST.WAKE,0,0,0,0),-4);s.flush();
    assert.equal(s.engineModule.calls.length,exports,name);assert.equal(s.engineModule.freed.length,freedAtReturn,name);assert.equal(s.collected.length,0,name);
  }
});

test('every Host callback during cached replay is terminal before callback dispatch or allocation cleanup',async()=>{
  for(const op of [...Object.values(OP),...Object.values(HOST)]){
    const access=[],s=documentReplayScenario({onEngineAccess:name=>access.push(name)});s.startDocument();const selector=s.offer(2,41n);s.flush();let freedAtEntry,accessAtEntry,kernelAtEntry,callbackResult;
    s.onReplay=()=>{freedAtEntry=s.engineModule.freed.length;accessAtEntry=access.length;kernelAtEntry=s.kernelModule.calls.length;callbackResult=s.bridge.callback(op,0,0,0,0);};
    const collections=s.collected.length,pending=s.bridge.replayDocumentCompletion(selector);s.flush();await assert.rejects(pending,terminal);
    assert.equal(callbackResult,-4);assert.equal(access.length,accessAtEntry,'callback must not read/validate/write endpoint arguments');assert.equal(s.kernelModule.calls.length,kernelAtEntry,'callback must not dispatch a kernel operation');
    assert.equal(s.bridge.state,'failed');assert.equal(s.engine.poisoned,true);assert.equal(s.engineModule.freed.length,freedAtEntry);assert.equal(s.collected.length,collections);
    const exports=s.engineModule.calls.length;s.bridge.poll();s.bridge.advance();s.flush();assert.equal(s.engineModule.calls.length,exports);
  }
});

test('cached replay traps malformed status joins counts and changed result bytes poison before cleanup',async()=>{
  for(const mode of ['trap','status','disposition','sequence','count','handled','bytes','identity','transfer','control','service','source']){
    const s=documentReplayScenario();s.startDocument();const selector=s.offer(2,41n);s.flush();let freedAtEntry;
    s.replayReply=(request,body)=>{
      freedAtEntry=s.engineModule.freed.length;if(mode==='trap')throw Error('cached replay trap');const view=new DataView(body.buffer);
      if(mode==='status')view.setInt32(0,-8,true);if(mode==='disposition')view.setUint32(4,2,true);if(mode==='sequence')view.setBigUint64(8,42n,true);
      if(mode==='count')view.setUint32(16,0,true);if(mode==='handled')view.setUint32(20,1,true);if(mode==='bytes')body[24+49]^=1;
      const raw=receipt(request,{payload:body,...(mode==='identity'?{identity:secondIdentity}:{}),...(mode==='transfer'?{transfer:request.transfer+1n}:{}),
        ...(mode==='control'?{control:CONTROL.STALE}:{}),...(mode==='service'?{service:2}:{})});
      if(mode==='source')new DataView(raw.buffer).setUint32(56,1,true);return raw;
    };
    const pending=s.bridge.replayDocumentCompletion(selector);s.flush();await assert.rejects(pending,terminal);assert.equal(s.bridge.state,'failed');
    assert.equal(s.engineModule.freed.length,freedAtEntry);assert.equal(s.collected.length,1);assert.equal(s.backendEntries,1);
  }
});

test('pending replay precedes an ordinary ACK and close or failure cancels it without native entry',async()=>{
  const s=documentReplayScenario();s.startDocument();const selector=s.offer(2,41n);s.flush();s.offer(3,42n);
  const pending=s.bridge.replayDocumentCompletion(selector);s.flush();await pending;assert.equal(s.cacheHits,1);assert.equal(s.metadataRetirements,1);
  await assert.rejects(s.bridge.replayDocumentCompletion(selector),/No exact/);
  for(const mode of ['close','failure']){
    const other=documentReplayScenario();other.startDocument();const owned=other.offer(2,41n);other.flush();const exports=other.engineModule.calls.length;
    const cancelled=other.bridge.replayDocumentCompletion(owned);
    if(mode==='close')assert.deepEqual(other.bridge.close(),{graceful:true});else assert.equal(other.bridge.callback(OP.SUBMIT,0,0,0,0),-4);
    await assert.rejects(cancelled,Error);other.flush();assert.equal(other.engineModule.calls.length,exports);assert.equal(other.cacheHits,0);
  }
});

test('navigation never retargets an owned replay and actual disposal evicts its original target',async()=>{
  const s=documentReplayScenario({abandonClosedDocumentOutcomes:true});s.startDocument();const selector=s.offer(2,41n);s.flush();s.navigate();s.flush();
  assert.deepEqual(s.bridge.identity,secondIdentity);const pending=s.bridge.replayDocumentCompletion(selector);s.flush();assert.deepEqual((await pending).identity,documentIdentity);
  assert.deepEqual(s.engineModule.calls.filter(request=>request.kind===ENGINE.COMMAND).at(-1).identity,documentIdentity);
  s.queuePruned(documentIdentity);s.bridge.poll();s.flush();assert.equal(s.disposed,1);await assert.rejects(s.bridge.replayDocumentCompletion(selector),/No exact/);
});

test('cached replay preserves ordinary high-water checks and the final exact ACK sequence',async()=>{
  for(const first of [41n,U64_MAX-1n]){
    const s=documentReplayScenario();s.startDocument();const form=s.offer(2,first);s.flush();let pending=s.bridge.replayDocumentCompletion(form);s.flush();await pending;
    const ack=s.offer(3,first+1n,{original:first});s.flush();pending=s.bridge.replayDocumentCompletion(ack);s.flush();await pending;
    assert.equal(s.bridge.state,'ready');assert.equal(s.backendEntries,1);assert.equal(s.metadataRetirements,1);
    if(first===41n){s.offer(2,43n);s.flush();assert.equal(s.backendEntries,2);const exports=s.engineModule.calls.length;s.offer(2,43n);s.flush();assert.equal(s.bridge.state,'failed');assert.equal(s.engineModule.calls.length,exports);}
  }
});

test('closing drains only exact owned physical context retirement without ordinary engine advance',async()=>{
 for(const action of [2,1]){
  const s=editorScenario({abandonClosedDocumentOutcomes:true});s.startEditor();
  let pending=true,done=false,closeCalls=0,commands=0;
  const body=new Uint8Array(88),view=new DataView(body.buffer);
  view.setUint32(0,3,true);view.setBigUint64(8,44n,true);
  body.set(Buffer.from('eef60cda2aa7b791641b0e5082d551ec37c10b8d92ca4cc71f13be0af45321d9','hex'),16);
  view.setUint32(48,16,true);view.setUint32(52,32,true);view.setUint32(56,action,true);
  view.setUint32(68,3,true);view.setBigUint64(80,7n,true);
  const kernel=s.hooks.kernel,engine=s.hooks.engine;
  s.hooks.kernel=(op,request)=>{
   if(op===OP.CLOSE){++closeCalls;return receipt(request,{service:done?0:2});}
   if(op===OP.PEEK_INPUT)return pending?receipt(request,{identity:documentIdentity,transfer:91n,payload:body}):receipt(request,{control:CONTROL.EMPTY});
   if(op===OP.COMMAND_RESULT){pending=false;done=true;assert.equal(request.transfer,91n);return receipt(request);}
   return kernel(op,request);
  };
  s.hooks.engine=(op,request)=>{
   if(op===ENGINE.COMMAND){++commands;s.turn(request);const result=new Uint8Array(24),v=new DataView(result.buffer);v.setUint32(4,1,true);v.setBigUint64(8,44n,true);return receipt(request,{payload:result});}
   return engine(op,request);
  };
  const before=s.engineModule.calls.filter(x=>x.kind===ENGINE.ADVANCE).length;
  assert.deepEqual(s.bridge.close(),{graceful:false,pending:true});s.flush();
  if(action===2){assert.equal(s.bridge.state,'closed');assert.equal(commands,1);assert.equal(done,true);assert.deepEqual(await s.bridge.closed,{graceful:true});assert.ok(closeCalls>=2);}
  else{assert.equal(s.bridge.state,'failed');assert.equal(commands,0);assert.match(s.failures[0].message,/Only owned physical context retirement/);}
  assert.equal(s.engineModule.calls.filter(x=>x.kind===ENGINE.ADVANCE).length,before);
 }
});

test('deferred copied close uses last-ready audit authority through live retirement and disposal',async()=>{
 const s=editorScenario({abandonClosedDocumentOutcomes:true});s.startEditor();
 let pending=true,phase='live',closes=0,commands=0;const audits=[];
 const body=new Uint8Array(88),view=new DataView(body.buffer);
 view.setUint32(0,3,true);view.setBigUint64(8,44n,true);
 body.set(Buffer.from('eef60cda2aa7b791641b0e5082d551ec37c10b8d92ca4cc71f13be0af45321d9','hex'),16);
 view.setUint32(48,16,true);view.setUint32(52,32,true);view.setUint32(56,2,true);
 view.setUint32(68,3,true);view.setBigUint64(80,7n,true);
 const kernel=s.hooks.kernel,engine=s.hooks.engine;
 s.hooks.kernel=(op,request)=>{
  if(op===OP.CLOSE){++closes;return receipt(request,{service:phase==='retired'&&s.disposed?0:2});}
  if(op===OP.PEEK_RETIREMENT_AUDIT||op===OP.PEEK_RETIRED_DOCUMENT){
   audits.push({op,phase,identity:{...request.identity}});
   if(Object.keys(documentIdentity).some(key=>request.identity[key]!==documentIdentity[key]))
    return receipt(request,{control:CONTROL.STALE,service:4});
   if(op===OP.PEEK_RETIREMENT_AUDIT)return receipt(request,{control:CONTROL.EMPTY,service:2});
  }
  if(op===OP.PEEK_INPUT)return pending?receipt(request,{identity:documentIdentity,transfer:91n,payload:body}):receipt(request,{control:CONTROL.EMPTY});
  if(op===OP.COMMAND_RESULT){pending=false;phase='retired';s.markCurrentClosed();s.queuePruned();return receipt(request);}
  return kernel(op,request);
 };
 s.hooks.engine=(op,request)=>{
  if(op===ENGINE.COMMAND){++commands;s.turn(request);const result=new Uint8Array(24),v=new DataView(result.buffer);v.setUint32(4,1,true);v.setBigUint64(8,44n,true);return receipt(request,{payload:result});}
  return engine(op,request);
 };
 assert.deepEqual(s.bridge.close(),{graceful:false,pending:true});s.flush();
 assert.equal(s.bridge.state,'closed','deferred Owner metadata must remain selectable until actual retirement completes');
 assert.deepEqual(await s.bridge.closed,{graceful:true});
 assert.equal(commands,1);assert.equal(s.disposed,1);assert.ok(closes>=2);
 assert.ok(audits.some(x=>x.phase==='live')&&audits.some(x=>x.phase==='retired'));
 assert.ok(audits.every(x=>Object.keys(documentIdentity).every(key=>x.identity[key]===documentIdentity[key])));
 assert.deepEqual(s.failures,[]);
 for(const control of [CONTROL.STALE,CONTROL.CONFLICT,CONTROL.CLOSED]){
  const f=editorScenario({abandonClosedDocumentOutcomes:true});f.startEditor();const normal=f.hooks.kernel;
  f.hooks.kernel=(op,request)=>op===OP.CLOSE?receipt(request,{service:2}):op===OP.PEEK_RETIREMENT_AUDIT?receipt(request,{control,service:2}):normal(op,request);
  f.bridge.close();f.flush();assert.equal(f.bridge.state,'failed');
  assert.match(f.failures[0].message,/Kernel terminal-outcome mailbox refused/);
 }
});

test('final native close witness precedes closed scheduler probes after exact retired disposal',async()=>{
 for(const earlyClosed of [false,true]){
  const s=editorScenario({abandonClosedDocumentOutcomes:true});s.startEditor();
  let phase='live',commands=0,closedProbes=0,finalWitnesses=0;
  const body=new Uint8Array(88),view=new DataView(body.buffer);
  view.setUint32(0,3,true);view.setBigUint64(8,44n,true);
  body.set(Buffer.from('eef60cda2aa7b791641b0e5082d551ec37c10b8d92ca4cc71f13be0af45321d9','hex'),16);
  view.setUint32(48,16,true);view.setUint32(52,32,true);view.setUint32(56,2,true);
  view.setUint32(68,3,true);view.setBigUint64(80,7n,true);
  const kernel=s.hooks.kernel,engine=s.hooks.engine;
  s.hooks.kernel=(op,request)=>{
   if(op===OP.CLOSE){
    if(phase==='retired'&&s.disposed){++finalWitnesses;return receipt(request,{service:0});}
    return receipt(request,{service:2});
   }
   if(op===OP.PEEK_INPUT){
    if(earlyClosed||phase==='retired'){++closedProbes;return receipt(request,{control:CONTROL.CLOSED,service:10});}
    return receipt(request,{identity:documentIdentity,transfer:91n,payload:body});
   }
   if(op===OP.COMMAND_RESULT){phase='retired';s.markCurrentClosed();s.queuePruned();return receipt(request);}
   return kernel(op,request);
  };
  s.hooks.engine=(op,request)=>{
   if(op===ENGINE.COMMAND){++commands;s.turn(request);const result=new Uint8Array(24),v=new DataView(result.buffer);v.setUint32(4,1,true);v.setBigUint64(8,44n,true);return receipt(request,{payload:result});}
   return engine(op,request);
  };
  assert.deepEqual(s.bridge.close(),{graceful:false,pending:true});s.flush();
  if(earlyClosed){
   assert.equal(s.bridge.state,'failed','CLOSED before an authentic final close witness must remain a refusal');
   assert.match(s.failures[0].message,/Physical input mailbox refused/);assert.equal(commands,0);assert.equal(finalWitnesses,0);
  }else{
   assert.equal(s.bridge.state,'closed','consume authentic native close after disposal before polling closed input');
   assert.deepEqual(await s.bridge.closed,{graceful:true});assert.equal(s.disposed,1);assert.equal(commands,1);
   assert.equal(finalWitnesses,1);assert.equal(closedProbes,0);assert.deepEqual(s.failures,[]);
  }
 }
});
