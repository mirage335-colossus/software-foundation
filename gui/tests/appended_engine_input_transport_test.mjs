// Production JavaScript transport with real, separate tiny Wasm memories.
// Allocators, native owner and engine dispatchers are explicit JS fakes. These
// checks execute no C++ owner, provider, WebCore/JSC, retained SDK or browser.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';

const moduleURL=process.argv[2]?pathToFileURL(resolve(process.argv[2])):new URL('../host/engine_kernel_bridge.mjs',import.meta.url);
const {BRIDGE_VERSION,HEADER_BYTES,RECEIPT_BYTES,MAX_SERVICE,OP,ENGINE,CONTROL,RESULT,HOST,
  DOCUMENT_WORK_PREFIX,DOCUMENT_BEGIN_BYTES,DOCUMENT_RESULT_PREFIX,MAX_DOCUMENT_RESULT,
  BridgeError,encodeRecord,decodeRecord,scalar32,scalar64,jsonBytes,createCopiedEndpoint,
  validateEngineProfile,validatePhysicalEngineProfile,inspectKernelPhysicalProfile,
  validateDocumentEngineProfile,inspectKernelDocumentProfile,createEngineKernelBridge}=await import(moduleURL.href);
const U64_MAX=(1n<<64n)-1n,workerEpoch=U64_MAX-1n;
const initial={worker:workerEpoch,instance:0n,document:0n,generation:0n};
const documentIdentity={worker:workerEpoch,instance:9007199254740993n,document:9007199254740995n,generation:9007199254740997n};
const nextIdentity={...documentIdentity,document:documentIdentity.document+2n,generation:documentIdentity.generation+2n};
const oldIdentity={...documentIdentity,document:documentIdentity.document-2n,generation:documentIdentity.generation-2n};
const commandTransfer=9007199254741001n,deliveryTransfer=commandTransfer+2n,ackTransfer=commandTransfer+4n,retirementTransfer=commandTransfer+6n;
const schemas=new Map([[1,'86b7baad1c95bfb8de3e6b7a9a7c433b528278bbcf84199ca0b2b4ee6134dbc9'],
  [3,'eef60cda2aa7b791641b0e5082d551ec37c10b8d92ca4cc71f13be0af45321d9'],
  [5,'6a15d0e2f814564ce263824dd782335bb327b886e982aefec32476a29b0fd4a3']]);
const terminal=error=>error instanceof BridgeError&&error.terminal===true;
const profile=()=>({schema_version:1,kind:'foundation-copied-engine-physical-v1',target:'browser-wasm32',
  binding:'copied-owner-bridge/direct-worker-physical-v1',pointer_bits:32,pthread:false,shared_memory:false,
  bridge_abi:BRIDGE_VERSION,capabilities:'467',contract_sha256:'1'.repeat(64),build_sha256:'2'.repeat(64),source_recipe_sha256:'3'.repeat(64),
  command_catalog_sha256:'d244e6a17561b49b937ad25058f2d662f4f86063633b716bdb87d0250796a47b',surface_protocol_version:1,surface_capabilities:'8225',mouse_input_version:1,
  key_mapping_version:1,viewport_width:800,viewport_height:600,display_scale:1});
const documentSchema='f11fd061350f8d663dbcdec7cf0a063e4fb0ff3564d285076690f58e8a84143d';
const actionAckSchema='1eb6c2d4f56acebc1423d9e2b5bf9a1717a99963a5c3f11f4b9d7b0fe33b50f5';
function documentProfile(physical=false){
  const value={schema_version:1,kind:'foundation-copied-engine-document-v2',target:'browser-wasm32',
    binding:'copied-owner-bridge/direct-worker-document-v2',pointer_bits:32,pthread:false,shared_memory:false,
    bridge_abi:BRIDGE_VERSION,capabilities:physical?'2003':'1795',
    contract_sha256:'aba7800e6aab1898f3614f0b1ac53e59b9f622bf1e9d3a413f50d672a3662298',
    build_sha256:'2'.repeat(64),source_recipe_sha256:'3'.repeat(64),provider_abi_major:1,provider_abi_minor:1,host_abi_major:1,host_abi_minor:0,
    document_profile:physical?'foundation-engine-copied2003-ndv2-v1':'foundation-engine-copied1795-ndv2-v1',
    base_header_sha256:'a8e89da85d34b29a4d1bc454495791fa604b81e3477e48ce8ca902e4333a9c0d',
    extension_header_sha256:'7b047bae4d0072ef156ea94ba637566d563fea3a95d43c4c6314afc919b1d626',
    document_catalog_sha256:'6e555d4c3bb71fbc965e1ca49671fab64d744913e18f45b9ba273505e0c6bcf5',
    document_schema_sha256:documentSchema,action_ack_schema_sha256:actionAckSchema,viewport_width:800,viewport_height:600};
  if(physical)Object.assign(value,{command_catalog_sha256:'d244e6a17561b49b937ad25058f2d662f4f86063633b716bdb87d0250796a47b',
    surface_protocol_version:1,surface_capabilities:'8225',mouse_input_version:1,key_mapping_version:1,display_scale:1});
  return value;
}

function tinyInstance(){
  const bytes=new Uint8Array([0,97,115,109,1,0,0,0,5,3,1,0,1,7,10,1,6,109,101,109,111,114,121,2,0]);
  return new WebAssembly.Instance(new WebAssembly.Module(bytes));
}
// Encode independently of the production codec, including the 72-byte header.
function receipt(request,{identity=request.identity,transfer=request.transfer,source=request.source,control=CONTROL.OK,service=0,payload=new Uint8Array()}={}){
  const bytes=new Uint8Array(RECEIPT_BYTES+payload.byteLength),view=new DataView(bytes.buffer);
  bytes.set([70,75,66,49]);view.setUint16(4,1,true);view.setUint16(6,request.kind|0x8000,true);view.setUint32(8,bytes.byteLength,true);
  ['worker','instance','document','generation'].forEach((key,i)=>view.setBigUint64(16+i*8,identity[key],true));
  view.setBigUint64(48,transfer,true);view.setUint32(56,source,true);view.setUint32(64,bytes.byteLength-HEADER_BYTES,true);
  view.setUint32(72,control,true);view.setUint32(76,service,true);bytes.set(payload,RECEIPT_BYTES);return bytes;
}
function command({operation=1,sequence=U64_MAX,payload=new Uint8Array(operation===1?33:operation===3?32:80)}={}){
  const bytes=new Uint8Array(56+payload.byteLength),view=new DataView(bytes.buffer);
  view.setUint32(0,operation,true);view.setBigUint64(8,sequence,true);
  const schema=schemas.get(operation);if(schema)bytes.set(Buffer.from(schema,'hex'),16);
  view.setUint32(48,16,true);view.setUint32(52,payload.byteLength,true);bytes.set(payload,56);return bytes;
}
function commandResult({status=0,disposition=1,sequence=U64_MAX,written=0,handled=1}={}){
  const bytes=new Uint8Array(24),view=new DataView(bytes.buffer);
  view.setInt32(0,status,true);view.setUint32(4,disposition,true);view.setBigUint64(8,sequence,true);
  view.setUint32(16,written,true);view.setUint32(20,handled,true);return bytes;
}
function mutate(bytes,offset,value,width=4){
  const copied=bytes.slice(),view=new DataView(copied.buffer);
  if(width===8)view.setBigUint64(offset,value,true);else if(width===2)view.setUint16(offset,value,true);else view.setUint32(offset,value,true);return copied;
}
function fakeModule(role,handler){
  const instance=tinyInstance(),allocations=[],freed=[],calls=[],exports=[];let next=128;
  const module={instance,allocations,freed,calls,exports,
    get HEAPU8(){return new Uint8Array(instance.exports.memory.buffer);},
    _malloc(length){exports.push('malloc');module.onAllocate?.(length);const pointer=next;next+=Math.max(length,1)+8;
      while(next>instance.exports.memory.buffer.byteLength)instance.exports.memory.grow(1);
      allocations.push({pointer,length});return pointer;},
    _free(pointer){exports.push('free');freed.push(pointer);module.onFree?.(pointer);},
    put(bytes){const pointer=module._malloc(bytes.byteLength);module.HEAPU8.set(bytes,pointer);return pointer;}};
  module[role==='kernel'?'_gui_web_engine_bridge_v1':'_bib_engine_wasm_bridge_v1']=()=>{exports.push('marker');return BRIDGE_VERSION;};
  module[role==='kernel'?'_gui_web_engine_dispatch_v1':'_bib_engine_wasm_dispatch_v1']=(op,p,n,out,cap)=>{
    exports.push('dispatch');const raw=new Uint8Array(module.HEAPU8.subarray(p,p+n));
    const request=decodeRecord(raw,{kind:op,receipt:false,maximum:raw.byteLength});calls.push(request);
    const result=handler?handler({op,request,out,cap,module}):receipt(request);
    if(!(result instanceof Uint8Array))return result;
    // A hostile return count may exceed capacity, but the fake never writes
    // outside the caller's span. Production must reject the oversized count.
    module.HEAPU8.set(result.subarray(0,cap),out);return result.byteLength;
  };
  return module;
}
function metadataModule(bytes=jsonBytes(profile())){
  const module=fakeModule('kernel');module.metadataCalls=[];
  module._gui_web_engine_input_describe_v1=(out,cap)=>{
    module.exports.push('describe');module.metadataCalls.push({out,cap});module.onDescribe?.(out,cap);
    if(bytes.byteLength<=cap)module.HEAPU8.set(bytes,out);return bytes.byteLength;
  };return module;
}

test('physical profile is a separate exact twenty-field successor; baseline validation stays exact 259',()=>{
  const original=profile(),validated=validatePhysicalEngineProfile(original);
  assert.deepEqual(validated,original);assert.equal(Object.isFrozen(validated),true);original.build_sha256='5'.repeat(64);assert.equal(validated.build_sha256,'2'.repeat(64));
  assert.throws(()=>validateEngineProfile(profile()),BridgeError);
  const baseline={...profile(),kind:'foundation-copied-engine-v1',binding:'copied-owner-bridge/direct-worker-v1',capabilities:'259'};
  for(const field of ['command_catalog_sha256','surface_protocol_version','surface_capabilities','mouse_input_version','key_mapping_version','viewport_width','viewport_height','display_scale'])delete baseline[field];
  assert.deepEqual(validateEngineProfile(baseline),baseline);assert.throws(()=>validatePhysicalEngineProfile(baseline),BridgeError);
  for(const patch of [{kind:'foundation-copied-engine-v1'},{binding:'copied-owner-bridge/direct-worker-v1'},{target:'native'},
    {pointer_bits:64},{pthread:true},{shared_memory:true},{bridge_abi:0},{capabilities:'259'},{capabilities:'0467'},
    {capabilities:467},{surface_capabilities:'8224'},{surface_capabilities:8225},{surface_protocol_version:2},{mouse_input_version:0},
    {key_mapping_version:0},{viewport_width:801},{viewport_height:601},{display_scale:2},{display_scale:NaN},
    {command_catalog_sha256:'F'.repeat(64)},{build_sha256:'0'.repeat(63)},{extra:true}])
    assert.throws(()=>validatePhysicalEngineProfile({...profile(),...patch}),BridgeError);
  for(const field of Object.keys(profile())){const missing=profile();delete missing[field];assert.throws(()=>validatePhysicalEngineProfile(missing),BridgeError);}
  for(const value of [null,[],Object.assign(Object.create(null),profile())])assert.throws(()=>validatePhysicalEngineProfile(value),BridgeError);
});
test('physical renderer projection rejects custom or null prototypes before any DOM access',async()=>{
  // Exercise the complete production bootstrap entry. Imports irrelevant to
  // this pre-DOM rejection are explicit inert fakes; no renderer is executed.
  const dataURL=source=>'data:text/javascript;base64,'+Buffer.from(source).toString('base64');
  const inert=dataURL('export function createEmbeddedFrontend(){throw Error("Unexpected frontend");}'+
    'export function createWasmTransport(){throw Error("Unexpected Worker");}'+
    'export function createHostChannel(){throw Error("Unexpected channel");}'+
    'export function validateSurfaceState(){throw Error("Unexpected state");}'+
    'export function validateSurfaceOperation(){throw Error("Unexpected operation");}'+
    'export function decodeAppendedBase64(){throw Error("Unexpected payload");}');
  let source=await readFile(new URL('./appended_engine_browser_bootstrap.mjs',moduleURL),'utf8');
  for(const name of ['browser_embedding','wasm_transport','renderer_channel','browser_surface_protocol','renderer_surface_child_bundle','appended_browser_bootstrap']){
    const edge="'./"+name+".mjs'";assert.equal(source.split(edge).length,2);source=source.replace(edge,JSON.stringify(inert));
  }
  const edge="'./engine_kernel_bridge.mjs'";assert.equal(source.split(edge).length,2);source=source.replace(edge,JSON.stringify(moduleURL.href));
  const {startAppendedEngineBrowser}=await import(dataURL(source));
  const fields={CHILD_SCRIPT:'retained',CHILD_SCRIPT_SHA256:'retained',CHILD_CSP:'retained',
    CHILD_SANDBOX:'allow-scripts',CHILD_PROTOCOL:'retained',CHILD_STYLE:'retained'};
  for(const prototype of [{custom:true},null]){
    let domReads=0;const host={get document(){++domReads;throw Error('Unexpected DOM access');}};
    await assert.rejects(startAppendedEngineBrowser({kernel:{kind:'foundation-copied-engine-physical-browser'},
      physicalRendererBundle:Object.assign(Object.create(prototype),fields),host}),/physical renderer bundle/);
    assert.equal(domReads,0);
  }
  let domReads=0;const host={get document(){++domReads;return {querySelector:()=>null};}};
  await assert.rejects(startAppendedEngineBrowser({kernel:{kind:'foundation-copied-engine-physical-browser'},physicalRendererBundle:{...fields},host}),/Missing retained browser mounts/);
  assert.ok(domReads>0,'a valid plain projection must pass the capture gate');
});
test('kernel physical description is read-only and copies through memory growth with one allocation/free',()=>{
  const module=metadataModule();module.onAllocate=()=>module.instance.exports.memory.grow(1);module.onDescribe=()=>module.instance.exports.memory.grow(1);
  assert.deepEqual(inspectKernelPhysicalProfile(module,profile()),profile());assert.deepEqual(module.exports,['malloc','describe','free']);
  assert.equal(module.allocations.length,1);assert.equal(module.allocations[0].length,4096);assert.equal(module.metadataCalls[0].cap,4096);
  assert.deepEqual(module.freed,[module.allocations[0].pointer]);assert.equal(module.calls.length,0);
});
test('kernel description rejects missing/mismatched facts and malformed bounded JSON before any dispatch',()=>{
  const missing=metadataModule();delete missing._gui_web_engine_input_describe_v1;assert.throws(()=>inspectKernelPhysicalProfile(missing,profile()),BridgeError);assert.equal(missing.allocations.length,0);
  for(const bytes of [jsonBytes({...profile(),build_sha256:'5'.repeat(64)}),jsonBytes({...profile(),extra:1}),
    new Uint8Array(),new Uint8Array([123]),new Uint8Array([0xff]),new Uint8Array([...jsonBytes(profile()),0]),
    new Uint8Array(4096).fill(32)]){
    const module=metadataModule(bytes);assert.throws(()=>inspectKernelPhysicalProfile(module,profile()),BridgeError);assert.equal(module.calls.length,0);
  }
});
test('kernel metadata count refusals free once while an export trap performs no cleanup exports',()=>{
  for(const count of [-1,0,4096,4097,1.5,undefined,Promise.resolve(1)]){
    const module=metadataModule();module._gui_web_engine_input_describe_v1=()=>{module.exports.push('describe');return count;};
    assert.throws(()=>inspectKernelPhysicalProfile(module,profile()),BridgeError);assert.equal(module.freed.length,1);assert.equal(module.calls.length,0);
  }
  const trapped=metadataModule();trapped._gui_web_engine_input_describe_v1=()=>{trapped.exports.push('describe');throw Error('metadata trap');};
  assert.throws(()=>inspectKernelPhysicalProfile(trapped,profile()),terminal);assert.deepEqual(trapped.exports,['malloc','describe']);assert.equal(trapped.freed.length,0);
});
test('kernel metadata allocation refusal, invalid spans and allocator/free traps fail without unsafe exports',()=>{
  const refused=metadataModule();refused._malloc=()=>0;
  assert.throws(()=>inspectKernelPhysicalProfile(refused,profile()),error=>error instanceof BridgeError&&error.code===CONTROL.LIMIT);
  assert.equal(refused.metadataCalls.length,0);assert.equal(refused.freed.length,0);
  for(const pointer of [-1,1.5,0xffffffff,0x100000000]){
    const module=metadataModule();module._malloc=()=>pointer;assert.throws(()=>inspectKernelPhysicalProfile(module,profile()),terminal);
    assert.equal(module.metadataCalls.length,0);assert.equal(module.freed.length,0);
  }
  const mallocTrap=metadataModule();mallocTrap._malloc=()=>{throw Error('malloc trap');};
  assert.throws(()=>inspectKernelPhysicalProfile(mallocTrap,profile()),terminal);assert.equal(mallocTrap.metadataCalls.length,0);assert.equal(mallocTrap.freed.length,0);
  const freeTrap=metadataModule();freeTrap.onFree=()=>{throw Error('free trap');};
  assert.throws(()=>inspectKernelPhysicalProfile(freeTrap,profile()),terminal);assert.equal(freeTrap.metadataCalls.length,1);assert.equal(freeTrap.freed.length,1);
});

function scenario({physical=true,abandonClosedDocumentOutcomes=false}={}){
  const tasks=[],events=[],failures=[],inputs=[],results=[],hooks={},timers=new Map();
  let bridge,current={...initial},nativeDepth=0,nextTimer=0,delivery=null,ack=null,retired=null,effects=0;
  const timer={setTimeout(fn){timers.set(++nextTimer,fn);return nextTimer;},clearTimeout(id){timers.delete(id);}};
  const selected=()=>{
    if(physical)return profile();const p=profile();p.kind='foundation-copied-engine-v1';p.binding='copied-owner-bridge/direct-worker-v1';p.capabilities='259';
    for(const key of ['command_catalog_sha256','surface_protocol_version','surface_capabilities','mouse_input_version','key_mapping_version','viewport_width','viewport_height','display_scale'])delete p[key];return p;
  };
  const kernelModule=fakeModule('kernel',({op,request})=>{
    events.push({role:'kernel',op,request});const override=hooks.kernel?.(op,request);if(override!==undefined)return override;
    switch(op){
      case OP.CONFIGURE:return receipt(request,{payload:jsonBytes({entry:'app://fixture/web/index.html'})});
      case OP.TURN_ENTER:++nativeDepth;return receipt(request);
      case OP.TURN_LEAVE:assert.ok(nativeDepth>0);--nativeDepth;return receipt(request);
      case OP.BEGIN_DOCUMENT:assert.ok(nativeDepth>0);current={...(request.identity.document===nextIdentity.document?nextIdentity:documentIdentity)};return receipt(request,{identity:current});
      case OP.CLOSE_DOCUMENT:assert.ok(nativeDepth>0);current={...current,document:0n,generation:0n};return receipt(request);
      case OP.PUMP_ONE:assert.equal(nativeDepth,0);if(ack)ack.applied=true;return receipt(request);
      case OP.PEEK_ACK_RECEIPT:return ack?.applied?receipt(request,{transfer:ackTransfer,payload:ack.payload}):receipt(request,{control:CONTROL.EMPTY});
      case OP.PEEK_DELIVERY:return delivery?receipt(request,{transfer:deliveryTransfer,payload:delivery}):receipt(request,{control:CONTROL.EMPTY});
      case OP.STAGE_ACK:ack??={applied:false,payload:new Uint8Array(12)};return receipt(request,{service:ack.applied?0:2});
      case OP.DELIVERY_RESULT:if(new DataView(request.payload.buffer).getUint32(0,true)===RESULT.ACCEPTED)delivery=null;return receipt(request);
      case OP.ACK_RECEIPT_RESULT:if(new DataView(request.payload.buffer).getUint32(0,true)===RESULT.ACCEPTED)ack=null;return receipt(request);
      case OP.PEEK_INPUT:{const value=inputs[0];return value?receipt(request,{payload:value.payload,identity:value.identity,transfer:value.transfer,source:value.source}):receipt(request,{control:CONTROL.EMPTY});}
      case OP.COMMAND_RESULT:assert.ok(inputs.length);results.push(request);inputs.shift();return receipt(request);
      case OP.PEEK_RETIREMENT_AUDIT:return receipt(request,{control:CONTROL.EMPTY});
      case OP.PEEK_RETIRED_DOCUMENT:return retired?receipt(request,{identity:oldIdentity,transfer:retirementTransfer}):receipt(request,{control:CONTROL.EMPTY});
      case OP.RETIRED_DOCUMENT_RESULT:retired=null;return receipt(request);
      case OP.CLOSE:return receipt(request);
      default:throw Error('Unexpected fake kernel operation '+op);
    }
  });
  const engineModule=fakeModule('engine',({op,request,cap})=>{
    events.push({role:'engine',op,request,cap});const override=hooks.engine?.(op,request,cap);if(override!==undefined)return override;
    if(op===ENGINE.DESCRIBE)return receipt(request,{payload:jsonBytes(selected())});
    if(op===ENGINE.START){guarded(request,()=>native(OP.BEGIN_DOCUMENT,new Uint8Array(),{...documentIdentity,generation:0n}));
      const bytes=new Uint8Array(8);new DataView(bytes.buffer).setUint32(4,2,true);return receipt(request,{identity:current,payload:bytes});}
    if(op===ENGINE.CURRENT_DOCUMENT){guarded(request,()=>{});return receipt(request,{identity:current});}
    if(op===ENGINE.ADVANCE){guarded(request,()=>hooks.advance?.());return receipt(request,{identity:current});}
    if(op===ENGINE.COMMAND){++effects;assert.equal(cap,RECEIPT_BYTES+24);const payload=guarded(request,()=>hooks.command?.(request)??commandResult({sequence:new DataView(request.payload.buffer).getBigUint64(8,true)}));
      return hooks.commandReceipt?.(request,payload)??receipt(request,{payload});}
    if(op===ENGINE.DELIVER_SERVICES){const disposition=guarded(request,()=>{native(OP.STAGE_ACK,scalar64(1n));return hooks.deliver?.()??RESULT.ACCEPTED;});return receipt(request,{payload:scalar32(disposition)});}
    if(op===ENGINE.COLLECT_ACK){guarded(request,()=>{});return receipt(request,{payload:scalar32(RESULT.ACCEPTED)});}
    if(op===ENGINE.DISPOSE_RETIRED){guarded(request,()=>{});return receipt(request,{payload:scalar32(0)});}
    throw Error('Unexpected fake engine operation '+op);
  });
  const kernel=createCopiedEndpoint(kernelModule,'kernel'),engine=createCopiedEndpoint(engineModule,'engine');
  function native(op,payload=new Uint8Array(),identity=current,transfer=0n){
    const bytes=encodeRecord(op,identity,payload,{transfer}),pointer=engineModule.put(bytes),output=engineModule._malloc(RECEIPT_BYTES+MAX_SERVICE);
    const length=bridge.callback(op,pointer,bytes.byteLength,output,RECEIPT_BYTES+MAX_SERVICE);
    if(length<0)throw new BridgeError('Fake native callback failed',{terminal:true});
    return decodeRecord(engine.read(output,length),{kind:op,worker:workerEpoch});
  }
  function guarded(request,action){native(OP.TURN_ENTER,new Uint8Array(),request.identity,request.transfer);const value=action();native(OP.TURN_LEAVE,new Uint8Array(),request.identity,request.transfer);return value;}
  bridge=createEngineKernelBridge({kernel,engine,workerEpoch,post:task=>tasks.push(task),timer,abandonClosedDocumentOutcomes,onFailure:error=>failures.push(error)});
  return {bridge,kernelModule,engineModule,kernel,engine,hooks,tasks,events,failures,results,inputs,native,
    start(){bridge.inspect(selected());bridge.configure(encodeRecord(OP.CONFIGURE,initial));bridge.start(selected(),{entry:'app://fixture/web/index.html'});this.flush();events.length=0;},
    queue(payload=command(),{identity=documentIdentity,transfer=commandTransfer,source=0}={}){inputs.push({payload,identity:{...identity},transfer,source});},
    queueService(){delivery=new Uint8Array([1,2,3]);},queueRetired(){retired=true;},
    step(){assert.ok(tasks.length,'expected scheduled owner task');tasks.shift()();},
    flush(limit=40){let count=0;while(tasks.length){assert.ok(count++<limit,'owner work must be bounded');this.step();}},
    get effects(){return effects;},get nativeDepth(){return nativeDepth;}};
}

test('physical polling is queued, carries maximum u64 unchanged, and collects one exact consumed result',()=>{
  const s=scenario();s.start();const bytes=command({payload:new Uint8Array(160).fill(37)});s.queue(bytes);
  s.bridge.poll();s.bridge.poll();s.bridge.poll();assert.equal(s.tasks.length,1);
  assert.equal(s.effects,0);assert.equal(s.results.length,0);assert.equal(s.events.length,0);s.flush();
  assert.equal(s.effects,1);assert.equal(s.results.length,1);assert.deepEqual(s.results[0].payload,commandResult());
  const entered=s.events.find(event=>event.role==='engine'&&event.op===ENGINE.COMMAND);
  assert.deepEqual(entered.request.payload,bytes);assert.deepEqual(entered.request.identity,documentIdentity);assert.equal(entered.request.transfer,commandTransfer);assert.equal(entered.request.source,0);
  assert.deepEqual(s.results[0].identity,documentIdentity);assert.equal(s.results[0].transfer,commandTransfer);assert.equal(s.nativeDepth,0);assert.deepEqual(s.failures,[]);
  s.bridge.poll();s.flush();assert.equal(s.effects,1);assert.equal(s.results.length,1);
});
test('each approved command operation uses its own frozen schema and payload bounds',()=>{
  for(const [operation,lengths] of [[1,[33,160]],[3,[32]],[5,[80]]])for(const length of lengths){
    const s=scenario();s.start();const bytes=command({operation,sequence:9007199254741011n,payload:new Uint8Array(length)});s.queue(bytes);s.bridge.poll();s.flush();
    assert.equal(s.bridge.state,'ready');assert.equal(s.effects,1);assert.equal(new DataView(s.results[0].payload.buffer).getBigUint64(8,true),9007199254741011n);
  }
});
test('physical engine inspection compares catalog facts and refuses changed profile before START',()=>{
  const mismatch=scenario();mismatch.hooks.engine=(op,request)=>op===ENGINE.DESCRIBE?receipt(request,{payload:jsonBytes({...profile(),command_catalog_sha256:'5'.repeat(64)})}):undefined;
  assert.throws(()=>mismatch.bridge.inspect(profile()),terminal);assert.equal(mismatch.kernelModule.calls.length,0);
  const changed=scenario();changed.bridge.inspect(profile());changed.bridge.configure(encodeRecord(OP.CONFIGURE,initial));
  assert.throws(()=>changed.bridge.start({...profile(),command_catalog_sha256:'5'.repeat(64)},{entry:'app://fixture/web/index.html'}),terminal);
  assert.equal(changed.engineModule.calls.some(request=>request.kind===ENGINE.START),false);
});
test('command sequences increase without precision loss and reject reuse, regression or wrap before effects',()=>{
  const previous=9007199254741009n;
  for(const [first,next] of [[previous,previous],[previous,previous-1n],[U64_MAX,1n]]){
    const s=scenario();s.start();s.queue(command({sequence:first}));s.bridge.poll();s.flush();assert.equal(s.effects,1);assert.equal(s.results.length,1);
    s.queue(command({sequence:next}),{transfer:commandTransfer+1n});s.bridge.poll();s.flush();
    assert.equal(s.bridge.state,'failed');assert.equal(s.effects,1);assert.equal(s.results.length,1);
  }
  const increasing=scenario();increasing.start();increasing.queue(command({sequence:previous}));increasing.queue(command({sequence:previous+1n}),{transfer:commandTransfer+1n});
  increasing.bridge.poll();increasing.flush();assert.equal(increasing.bridge.state,'ready');assert.equal(increasing.effects,2);
  assert.deepEqual(increasing.results.map(request=>new DataView(request.payload.buffer).getBigUint64(8,true)),[previous,previous+1n]);
});
test('consumed handled zero is collected once without a fallback or engine replay',()=>{
  const s=scenario();s.start();s.hooks.command=()=>commandResult({handled:0});s.queue();s.bridge.poll();s.flush();
  assert.equal(s.bridge.state,'ready');assert.equal(s.effects,1);assert.deepEqual(s.results[0].payload,commandResult({handled:0}));
  for(let i=0;i<3;++i){s.bridge.poll();s.flush();}assert.equal(s.effects,1);assert.equal(s.results.length,1);
});
test('explicit provider rejection is forwarded unchanged without replay',()=>{
  for(const status of [-1,-7]){
    const s=scenario();s.start();const result=commandResult({status,disposition:0,handled:0});s.hooks.command=()=>result;s.queue();s.bridge.poll();s.flush();
    assert.equal(s.bridge.state,'ready');assert.equal(s.effects,1);assert.deepEqual(s.results[0].payload,result);s.bridge.poll();s.flush();assert.equal(s.effects,1);
  }
});
test('uncertain consumption or status minus eight reports the exact outcome once then terminates',()=>{
  for(const [status,disposition] of [[-1,2],[-8,0],[-8,2]]){
    const s=scenario();s.start();const result=commandResult({status,disposition,handled:0});s.hooks.command=()=>result;s.queue();const freed=s.engineModule.freed.length;s.bridge.poll();s.flush();
    assert.equal(s.bridge.state,'failed');assert.equal(s.effects,1);assert.equal(s.results.length,1);assert.deepEqual(s.results[0].payload,result);assert.equal(s.failures.length,1);
    assert.equal(s.engine.poisoned,true);assert.equal(s.engineModule.freed.length,freed,'unknown consumption must not reenter the engine through free');
    const calls=s.engineModule.calls.length;s.bridge.poll();s.flush();assert.equal(s.engineModule.calls.length,calls);assert.equal(s.results.length,1);
  }
});
test('malformed command envelopes and authority fail before any engine command effect',()=>{
  const valid=command(),badBodies=[valid.subarray(0,55),mutate(valid,0,0),mutate(valid,0,2),mutate(valid,4,1),mutate(valid,8,0n,8),
    mutate(valid,16,0),mutate(valid,48,15),mutate(valid,48,17),mutate(valid,52,34),command({payload:new Uint8Array(32)}),command({payload:new Uint8Array(161)}),
    command({operation:3,payload:new Uint8Array(31)}),command({operation:3,payload:new Uint8Array(33)}),command({operation:5,payload:new Uint8Array(79)}),command({operation:5,payload:new Uint8Array(81)})];
  for(const payload of badBodies){const s=scenario();s.start();s.queue(payload);s.bridge.poll();s.flush();assert.equal(s.bridge.state,'failed');assert.equal(s.effects,0);assert.equal(s.results.length,0);}
  for(const options of [{source:1},{source:2},{transfer:0n},{identity:{...documentIdentity,instance:0n}},
    {identity:{...documentIdentity,document:0n}},{identity:{...documentIdentity,generation:0n}},{identity:nextIdentity}]){
    const s=scenario();s.start();s.queue(valid,options);s.bridge.poll();s.flush();assert.equal(s.bridge.state,'failed');assert.equal(s.effects,0);assert.equal(s.results.length,0);
  }
});
test('malformed provider result bodies terminate without inventing a native outcome',()=>{
  const valid=commandResult(),invalid=[valid.subarray(0,23),new Uint8Array(25),commandResult({status:1}),commandResult({status:-9}),
    commandResult({disposition:0}),commandResult({disposition:2}),commandResult({disposition:3}),commandResult({status:-1,disposition:1,handled:0}),
    commandResult({sequence:U64_MAX-1n}),commandResult({sequence:0n}),commandResult({written:1}),commandResult({handled:2}),commandResult({status:-1,disposition:0,handled:1})];
  for(const result of invalid){const s=scenario();s.start();s.hooks.command=()=>result;s.queue();s.bridge.poll();s.flush();
    assert.equal(s.bridge.state,'failed');assert.equal(s.effects,1);assert.equal(s.results.length,0);assert.equal(s.failures.length,1);}
});
test('command result requires matching source, complete target, transfer and common statuses',()=>{
  for(const patch of [{source:1},{identity:nextIdentity},{identity:{...documentIdentity,worker:1n}},{transfer:commandTransfer+1n},
    {control:CONTROL.STALE},{service:1}]){
    const s=scenario();s.start();s.hooks.commandReceipt=(request,payload)=>receipt(request,{payload,...patch});s.queue();s.bridge.poll();s.flush();
    assert.equal(s.bridge.state,'failed');assert.equal(s.effects,1);assert.equal(s.results.length,0);
  }
});
test('native result collection refusal terminates after one effect and never retries the command',()=>{
  for(const patch of [{control:CONTROL.STALE},{service:2},{source:1},{identity:nextIdentity},{transfer:commandTransfer+1n},{payload:new Uint8Array([1])}]){
    const s=scenario();s.start();let collections=0;
    s.hooks.kernel=(op,request)=>{if(op===OP.COMMAND_RESULT){++collections;return receipt(request,patch);}};
    s.queue();s.bridge.poll();s.flush();assert.equal(s.bridge.state,'failed');assert.equal(s.effects,1);assert.equal(collections,1);
    const engineCalls=s.engineModule.calls.length;s.bridge.poll();s.flush();assert.equal(s.engineModule.calls.length,engineCalls);assert.equal(collections,1);
  }
});
test('engine command trap poisons the endpoint and executes neither cleanup exports nor replay',()=>{
  const s=scenario();s.start();s.hooks.engine=op=>{if(op===ENGINE.COMMAND)throw Error('command trap');};s.queue();const freed=s.engineModule.freed.length;
  s.bridge.poll();s.flush();assert.equal(s.bridge.state,'failed');assert.equal(s.engine.poisoned,true);assert.equal(s.engineModule.freed.length,freed);assert.equal(s.results.length,0);
  const exports=s.engineModule.exports.length;s.bridge.poll();s.flush();assert.equal(s.engineModule.exports.length,exports);
});
test('outstanding service delivery and ACK receipt settle before physical command entry',()=>{
  const s=scenario();s.start();s.queueService();s.queue();s.bridge.poll();s.step();assert.equal(s.effects,0);
  s.step();assert.equal(s.effects,0);s.step();assert.equal(s.effects,0);s.step();assert.equal(s.effects,0);s.flush();
  const commandIndex=s.events.findIndex(event=>event.role==='engine'&&event.op===ENGINE.COMMAND);
  const ackIndex=s.events.findIndex(event=>event.role==='kernel'&&event.op===OP.ACK_RECEIPT_RESULT);
  assert.ok(ackIndex>=0&&commandIndex>ackIndex);assert.equal(s.effects,1);assert.deepEqual(s.failures,[]);
});
test('rejected service completion blocks physical input until the owner explicitly retries it',()=>{
  const s=scenario();s.start();let reject=true;s.hooks.deliver=()=>reject?RESULT.REJECTED:RESULT.ACCEPTED;s.queueService();s.queue();s.bridge.poll();s.flush();
  assert.equal(s.effects,0);s.bridge.poll();s.flush();assert.equal(s.effects,0);reject=false;s.bridge.retryDelivery();s.flush();assert.equal(s.effects,1);assert.equal(s.results.length,1);
});
test('exact native service wait drains the focus retirement command before its suspended effect',()=>{
  const s=scenario();s.start();let waiting=true,pendingEffect=true,nativeServiceEffects=0;
  const focus=new Uint8Array(32),focusView=new DataView(focus.buffer);
  focusView.setUint32(0,2,true);focusView.setUint32(12,1,true);focusView.setBigUint64(24,9007199254741017n,true);
  s.hooks.kernel=(op,request)=>{
    if(op===OP.PUMP_ONE){
      if(waiting)return receipt(request,{control:CONTROL.CONFLICT,service:2});
      if(pendingEffect){pendingEffect=false;++nativeServiceEffects;}
    }
    if(op===OP.COMMAND_RESULT){assert.equal(nativeServiceEffects,0);waiting=false;}
  };
  s.hooks.command=request=>{assert.equal(nativeServiceEffects,0);assert.equal(new DataView(request.payload.buffer).getUint32(0,true),3);assert.deepEqual(request.payload.subarray(56),focus);return commandResult();};
  s.queue(command({operation:3,payload:focus}));s.bridge.advance();assert.equal(nativeServiceEffects,0);s.flush();
  assert.equal(s.bridge.state,'ready');assert.equal(s.effects,1);assert.equal(s.results.length,1);assert.equal(nativeServiceEffects,1);
  const resultIndex=s.events.findIndex(event=>event.role==='kernel'&&event.op===OP.COMMAND_RESULT);
  const advanceIndex=s.events.findIndex(event=>event.role==='engine'&&event.op===ENGINE.ADVANCE);
  assert.ok(advanceIndex>resultIndex);assert.deepEqual(s.failures,[]);
});
test('a suspended service with no input neither advances the engine nor spins its owner queue',()=>{
  const s=scenario();s.start();s.hooks.kernel=(op,request)=>op===OP.PUMP_ONE?receipt(request,{control:CONTROL.CONFLICT,service:2}):undefined;
  s.bridge.advance();s.flush();assert.equal(s.bridge.state,'ready');assert.equal(s.effects,0);assert.equal(s.tasks.length,0);
  assert.equal(s.events.some(event=>event.role==='engine'&&event.op===ENGINE.ADVANCE),false);
  assert.equal(s.events.filter(event=>event.role==='kernel'&&event.op===OP.PEEK_INPUT).length,1);
});
test('only the exact physical native service wait status permits input inspection',()=>{
  for(const [physical,control,service] of [[true,CONTROL.CONFLICT,0],[true,CONTROL.INVALID,2],[true,CONTROL.INTERNAL,2],[false,CONTROL.CONFLICT,2]]){
    const s=scenario({physical});s.start();s.hooks.kernel=(op,request)=>op===OP.PUMP_ONE?receipt(request,{control,service}):undefined;s.queue();s.bridge.poll();s.flush();
    assert.equal(s.bridge.state,'failed');assert.equal(s.effects,0);assert.equal(s.events.some(event=>event.role==='kernel'&&event.op===OP.PEEK_INPUT),false);
  }
});
test('retired document disposal completes before physical input is peeked or entered',()=>{
  const s=scenario({abandonClosedDocumentOutcomes:true});s.start();s.queueRetired();s.queue();s.bridge.poll();s.step();assert.equal(s.effects,0);s.flush();
  const retiredIndex=s.events.findIndex(event=>event.role==='kernel'&&event.op===OP.RETIRED_DOCUMENT_RESULT);
  const inputIndex=s.events.findIndex(event=>event.role==='kernel'&&event.op===OP.PEEK_INPUT);
  assert.ok(retiredIndex>=0&&inputIndex>retiredIndex);assert.equal(s.effects,1);assert.deepEqual(s.failures,[]);
});
test('command entry bars reentrant advance and close and retains captured authority through navigation',()=>{
  const s=scenario();s.start();s.hooks.command=request=>{
    assert.equal(s.bridge.advance(),false);assert.deepEqual(s.bridge.close(),{graceful:false});
    s.native(OP.CLOSE_DOCUMENT,new Uint8Array(),request.identity,request.transfer);
    s.native(OP.BEGIN_DOCUMENT,new Uint8Array(),{...nextIdentity,generation:0n},request.transfer);return commandResult();
  };
  s.queue();s.bridge.poll();s.flush();assert.deepEqual(s.bridge.identity,nextIdentity);assert.equal(s.effects,1);assert.equal(s.results.length,1);
  assert.deepEqual(s.results[0].identity,documentIdentity);assert.equal(s.results[0].transfer,commandTransfer);
  const leave=s.events.filter(event=>event.role==='kernel'&&event.op===OP.TURN_LEAVE).at(-1);
  assert.deepEqual(leave.request.identity,documentIdentity);assert.equal(leave.request.transfer,commandTransfer);assert.deepEqual(s.failures,[]);
});
test('baseline 259 bridge never advertises or polls the physical mailbox',()=>{
  const s=scenario({physical:false});s.start();s.queue();s.bridge.poll();s.flush();
  assert.equal(s.effects,0);assert.equal(s.events.some(event=>event.role==='kernel'&&event.op===OP.PEEK_INPUT),false);assert.equal(s.bridge.state,'ready');
});
test('closing before a queued poll prevents command entry and all later engine exports',()=>{
  const s=scenario();s.start();s.queue();s.bridge.poll();assert.equal(s.tasks.length,1);
  assert.deepEqual(s.bridge.close(),{graceful:true});const calls=s.engineModule.calls.length;s.flush();
  assert.equal(s.bridge.state,'closed');assert.equal(s.effects,0);assert.equal(s.results.length,0);assert.equal(s.engineModule.calls.length,calls);
  assert.equal(s.bridge.poll(),false);assert.equal(s.tasks.length,0);
});

// NDV2 packets below are opaque transport data. The real semantic decoder,
// native provider effects and browser DOM are not substituted by this fixture.
function documentPacket(kind,{identity=documentIdentity,sequence=9007199254741101n,
  token=kind===1||kind===4?9007199254741117n:0n,length=kind===1||kind===4?48:kind===2?81:52}={}){
  const bytes=new Uint8Array(length),view=new DataView(bytes.buffer);bytes.set([78,68,86,50]);
  view.setUint16(4,2,true);view.setUint16(6,kind,true);
  view.setBigUint64(8,identity.instance,true);view.setBigUint64(16,identity.generation,true);view.setBigUint64(24,identity.document,true);
  view.setBigUint64(32,sequence,true);view.setBigUint64(40,token,true);return bytes;
}
function documentWork({kind=1,operation=kind===1?3:kind===2?6:7,sequence=9007199254741101n,
  payload=kind===1||kind===2?documentPacket(kind,{sequence}):scalar64(sequence-1n),
  schema=kind===3?actionAckSchema:documentSchema,capacity=kind===3?16:1048576}={}){
  const bytes=new Uint8Array(56+payload.byteLength),view=new DataView(bytes.buffer);
  view.setUint32(0,kind,true);view.setUint32(4,operation,true);view.setBigUint64(8,sequence,true);
  bytes.set(Buffer.from(schema,'hex'),16);view.setUint32(48,capacity,true);view.setUint32(52,payload.byteLength,true);bytes.set(payload,56);return bytes;
}
function queryResult({status=0,revision=9007199254741123n,packet=documentPacket(4),written=packet.byteLength}={}){
  const bytes=new Uint8Array(16+packet.byteLength),view=new DataView(bytes.buffer);
  view.setInt32(0,status,true);view.setUint32(4,written,true);view.setBigUint64(8,revision,true);bytes.set(packet,16);return bytes;
}
function documentCommandResult({sequence=9007199254741101n,status=0,disposition=1,handled=1,
  packet=documentPacket(5,{sequence}),written=packet.byteLength}={}){
  const bytes=new Uint8Array(24+packet.byteLength);bytes.set(commandResult({sequence,status,disposition,handled,written}));bytes.set(packet,24);return bytes;
}
function actionAckResult(original,code=0){
  const bytes=new Uint8Array(16),view=new DataView(bytes.buffer);view.setBigUint64(0,original,true);view.setUint32(8,code,true);return bytes;
}
function documentMetadataModule(value=documentProfile()){
  const module=fakeModule('kernel');module.metadataCalls=[];
  module._gui_web_engine_document_describe_v1=(out,cap)=>{
    module.exports.push('document-describe');module.metadataCalls.push({out,cap});module.onDescribe?.(out,cap);
    const bytes=value instanceof Uint8Array?value:jsonBytes(value);
    if(bytes.byteLength<=cap)module.HEAPU8.set(bytes,out);return bytes.byteLength;
  };return module;
}
function documentScenario({physical=false}={}){
  const tasks=[],events=[],failures=[],work=[],physicalInputs=[],claims=[],results=[],physicalResults=[],hooks={},timers=new Map();
  let bridge,current={...initial},depth=0,nextTimer=0,queryCalls=0,formCalls=0,ackCalls=0,physicalCalls=0;
  const timer={setTimeout(task){timers.set(++nextTimer,task);return nextTimer;},clearTimeout(id){timers.delete(id);}};
  const kernelModule=fakeModule('kernel',({op,request,cap})=>{
    events.push({role:'kernel',op,request,cap});const override=hooks.kernel?.(op,request,cap);if(override!==undefined)return override;
    switch(op){
      case OP.CONFIGURE:return receipt(request,{payload:jsonBytes({entry:'app://fixture/web/index.html'})});
      case OP.TURN_ENTER:++depth;return receipt(request);
      case OP.TURN_LEAVE:assert.ok(depth>0);--depth;return receipt(request);
      case OP.BEGIN_DOCUMENT:assert.ok(depth>0);current={...(request.identity.document===nextIdentity.document?nextIdentity:documentIdentity)};return receipt(request,{identity:current});
      case OP.CLOSE_DOCUMENT:assert.ok(depth>0);current={...current,document:0n,generation:0n};return receipt(request);
      case OP.PUMP_ONE:assert.equal(depth,0);return receipt(request);
      case OP.PEEK_ACK_RECEIPT:case OP.PEEK_DELIVERY:case OP.PEEK_RETIREMENT_AUDIT:case OP.PEEK_RETIRED_DOCUMENT:
        return receipt(request,{control:CONTROL.EMPTY});
      case OP.PEEK_DOCUMENT_WORK:{const value=work[0];return value?receipt(request,value):receipt(request,{control:CONTROL.EMPTY});}
      case OP.BEGIN_DOCUMENT_WORK:
        assert.equal(depth,0);assert.ok(work.length);claims.push(request);return receipt(request);
      case OP.DOCUMENT_WORK_RESULT:
        assert.equal(depth,0,'document result must follow the complete native turn/export');assert.ok(work.length);
        results.push(request);work.shift();return receipt(request);
      case OP.PEEK_INPUT:{const value=physicalInputs[0];return value?receipt(request,value):receipt(request,{control:CONTROL.EMPTY});}
      case OP.COMMAND_RESULT:assert.ok(physicalInputs.length);physicalResults.push(request);physicalInputs.shift();return receipt(request);
      case OP.CLOSE:return receipt(request);
      default:throw Error('Unexpected document kernel operation '+op);
    }
  });
  const engineModule=fakeModule('engine',({op,request,cap})=>{
    events.push({role:'engine',op,request,cap});const override=hooks.engine?.(op,request,cap);if(override!==undefined)return override;
    if(op===ENGINE.DESCRIBE)return receipt(request,{payload:jsonBytes(documentProfile(physical))});
    if(op===ENGINE.START){guarded(request,()=>native(OP.BEGIN_DOCUMENT,new Uint8Array(),{...documentIdentity,generation:0n}));
      const bytes=new Uint8Array(8);new DataView(bytes.buffer).setUint32(4,2,true);return receipt(request,{identity:current,payload:bytes});}
    if(op===ENGINE.CURRENT_DOCUMENT){guarded(request,()=>{});return receipt(request,{identity:current});}
    if(op===ENGINE.ADVANCE){guarded(request,()=>hooks.advance?.());return receipt(request,{identity:current});}
    if(op===ENGINE.QUERY){++queryCalls;assert.equal(cap,1048672);
      const view=new DataView(request.payload.buffer,request.payload.byteOffset,request.payload.byteLength);
      const packet=documentPacket(4,{identity:request.identity,sequence:view.getBigUint64(80,true),token:view.getBigUint64(88,true)});
      const payload=guarded(request,()=>hooks.query?.(request)??queryResult({packet}));
      return hooks.providerReceipt?.(op,request,payload)??receipt(request,{payload});}
    if(op===ENGINE.COMMAND){
      const view=new DataView(request.payload.buffer,request.payload.byteOffset,request.payload.byteLength),operation=view.getUint32(0,true),sequence=view.getBigUint64(8,true);
      let payload;
      if(operation===6){++formCalls;assert.equal(cap,1048680);payload=guarded(request,()=>hooks.form?.(request)??documentCommandResult({sequence}));}
      else if(operation===7){++ackCalls;assert.equal(cap,120);assert.equal(depth,0);
        const original=view.getBigUint64(56,true);payload=hooks.ack?.(request)??documentCommandResult({sequence,handled:0,packet:actionAckResult(original)});}
      else{++physicalCalls;assert.equal(cap,104);payload=guarded(request,()=>hooks.physical?.(request)??commandResult({sequence}));}
      return hooks.providerReceipt?.(op,request,payload)??receipt(request,{payload});
    }
    throw Error('Unexpected document engine operation '+op);
  });
  const kernel=createCopiedEndpoint(kernelModule,'kernel'),engine=createCopiedEndpoint(engineModule,'engine');
  function native(op,payload=new Uint8Array(),identity=current,transfer=0n){
    const bytes=encodeRecord(op,identity,payload,{transfer}),pointer=engineModule.put(bytes),out=engineModule._malloc(RECEIPT_BYTES);
    const length=bridge.callback(op,pointer,bytes.byteLength,out,RECEIPT_BYTES);
    if(length<0)throw new BridgeError('Document native callback failed',{terminal:true});
    return decodeRecord(engine.read(out,length),{kind:op,worker:workerEpoch});
  }
  function guarded(request,action){native(OP.TURN_ENTER,new Uint8Array(),request.identity,request.transfer);
    const value=action();native(OP.TURN_LEAVE,new Uint8Array(),request.identity,request.transfer);return value;}
  bridge=createEngineKernelBridge({kernel,engine,workerEpoch,post:task=>tasks.push(task),timer,onFailure:error=>failures.push(error)});
  return {bridge,kernelModule,engineModule,kernel,engine,hooks,tasks,events,failures,work,claims,results,physicalResults,native,guarded,
    start(){const profile=documentProfile(physical);bridge.inspect(profile);bridge.configure(encodeRecord(OP.CONFIGURE,initial));
      bridge.start(profile,{entry:'app://fixture/web/index.html'});this.flush();events.length=0;},
    queue(payload=documentWork(),{identity=documentIdentity,transfer=commandTransfer,source=0}={}){
      work.push({payload,identity:{...identity},transfer,source});},
    queuePhysical(payload=command({sequence:9007199254741101n}),{identity=documentIdentity,transfer=commandTransfer+1n,source=0}={}){
      physicalInputs.push({payload,identity:{...identity},transfer,source});},
    step(){assert.ok(tasks.length,'expected document owner task');tasks.shift()();},
    flush(limit=40){let count=0;while(tasks.length){assert.ok(count++<limit,'document owner work must be bounded');this.step();}},
    get queryCalls(){return queryCalls;},get formCalls(){return formCalls;},get ackCalls(){return ackCalls;},
    get physicalCalls(){return physicalCalls;},get depth(){return depth;}};
}
function documentCallbackScratch(s,operation){
  const raw=encodeRecord(operation,documentIdentity,new Uint8Array(),{transfer:commandTransfer});
  const input=s.engineModule.put(raw),output=s.engineModule._malloc(RECEIPT_BYTES);
  return ()=>s.bridge.callback(operation,input,raw.byteLength,output,RECEIPT_BYTES);
}
function closeCurrentDocument(s){
  s.hooks.kernel=(op,request)=>{
    if(op===OP.PUMP_ONE&&!s.bridge.identity.generation)return receipt(request,{control:CONTROL.STALE});
  };
  s.hooks.advance=()=>{s.native(OP.CLOSE_DOCUMENT);s.hooks.advance=undefined;};
  assert.equal(s.bridge.advance(),true);s.flush();
  assert.equal(s.bridge.state,'ready');assert.deepEqual(s.bridge.identity,{...documentIdentity,document:0n,generation:0n});
  assert.equal(s.events.filter(value=>value.role==='kernel'&&value.op===OP.CLOSE_DOCUMENT).length,1);
  assert.equal(s.depth,0);s.events.length=0;
}

test('document profiles are exact separate 24/30-field contracts, never legacy profile upgrades',()=>{
  for(const physical of [false,true]){
    const original=documentProfile(physical),validated=validateDocumentEngineProfile(original);
    assert.equal(Object.keys(original).length,physical?30:24);assert.deepEqual(validated,original);assert.equal(Object.isFrozen(validated),true);
    original.build_sha256='4'.repeat(64);assert.equal(validated.build_sha256,'2'.repeat(64));
    assert.throws(()=>validateEngineProfile(validated),BridgeError);assert.throws(()=>validatePhysicalEngineProfile(validated),BridgeError);
    for(const key of Object.keys(validated)){const missing={...validated};delete missing[key];assert.throws(()=>validateDocumentEngineProfile(missing),BridgeError);}
    for(const patch of [{extra:1},{provider_abi_minor:0},{provider_abi_minor:2},{host_abi_minor:1},{capabilities:'259'},{capabilities:'467'},
      {capabilities:physical?'1795':'2003'},{capabilities:1795},{capabilities:'01795'},{pointer_bits:64},{pthread:true},{shared_memory:true},
      {build_sha256:'0'.repeat(64)},{source_recipe_sha256:'0'.repeat(64)},{base_header_sha256:'0'.repeat(64)},
      {extension_header_sha256:'1'.repeat(64)},{contract_sha256:'2'.repeat(64)},{document_catalog_sha256:'3'.repeat(64)},
      {document_schema_sha256:'4'.repeat(64)},{action_ack_schema_sha256:'5'.repeat(64)},{viewport_width:801},{viewport_height:601}])
      assert.throws(()=>validateDocumentEngineProfile({...validated,...patch}),BridgeError);
    if(physical)for(const patch of [{command_catalog_sha256:'0'.repeat(64)},{surface_protocol_version:2},{surface_capabilities:'8224'},
      {mouse_input_version:0},{key_mapping_version:2},{display_scale:2}])assert.throws(()=>validateDocumentEngineProfile({...validated,...patch}),BridgeError);
    else assert.throws(()=>validateDocumentEngineProfile({...validated,display_scale:1}),BridgeError);
    for(const prototype of [null,{custom:true}])assert.throws(()=>validateDocumentEngineProfile(Object.assign(Object.create(prototype),validated)),BridgeError);
  }
  assert.throws(()=>validateDocumentEngineProfile(profile()),BridgeError);
  const old={...profile(),kind:'foundation-copied-engine-v1',binding:'copied-owner-bridge/direct-worker-v1',capabilities:'259'};
  for(const key of ['command_catalog_sha256','surface_protocol_version','surface_capabilities','mouse_input_version','key_mapping_version','viewport_width','viewport_height','display_scale'])delete old[key];
  assert.deepEqual(validateEngineProfile(old),old);assert.deepEqual(validatePhysicalEngineProfile(profile()),profile());
  assert.throws(()=>validateDocumentEngineProfile(old),BridgeError);
});
test('document compiled facts use their own read-only getter and copy through memory growth',()=>{
  for(const physical of [false,true]){
    const expected=documentProfile(physical),module=documentMetadataModule(expected);
    module.onAllocate=()=>module.instance.exports.memory.grow(1);module.onDescribe=()=>module.instance.exports.memory.grow(1);
    assert.deepEqual(inspectKernelDocumentProfile(module,expected),expected);
    assert.deepEqual(module.exports,['malloc','document-describe','free']);assert.equal(module.metadataCalls[0].cap,4096);
    assert.equal(module.allocations.length,1);assert.equal(module.freed.length,1);assert.equal(module.calls.length,0);
  }
  const legacy=metadataModule();assert.throws(()=>inspectKernelDocumentProfile(legacy,documentProfile()),BridgeError);
  assert.equal(legacy.allocations.length,0,'a physical getter cannot stand in for missing document facts');
  for(const value of [new Uint8Array(),new Uint8Array([123]),new Uint8Array([0xff]),new Uint8Array([...jsonBytes(documentProfile()),0]),
    new Uint8Array(4096).fill(32),{...documentProfile(),build_sha256:'5'.repeat(64)},{...documentProfile(),extra:1}]){
    const module=documentMetadataModule(value);assert.throws(()=>inspectKernelDocumentProfile(module,documentProfile()),BridgeError);assert.equal(module.calls.length,0);
  }
});
test('document metadata refusal frees once while getter traps perform no later exports',()=>{
  for(const count of [-1,0,4096,4097,1.5,undefined,Promise.resolve(1)]){
    const module=documentMetadataModule();module._gui_web_engine_document_describe_v1=()=>count;
    assert.throws(()=>inspectKernelDocumentProfile(module,documentProfile()),BridgeError);assert.equal(module.freed.length,1);assert.equal(module.calls.length,0);
  }
  const trapped=documentMetadataModule();trapped._gui_web_engine_document_describe_v1=()=>{trapped.exports.push('document-describe');throw Error('document getter trap');};
  assert.throws(()=>inspectKernelDocumentProfile(trapped,documentProfile()),terminal);
  assert.deepEqual(trapped.exports,['malloc','document-describe']);assert.equal(trapped.freed.length,0);assert.equal(trapped.calls.length,0);
});
test('only document result28 widens the unchanged service body limit and uses literal mailbox layouts',()=>{
  assert.equal(OP.PEEK_DOCUMENT_WORK,27);assert.equal(OP.DOCUMENT_WORK_RESULT,28);assert.equal(OP.BEGIN_DOCUMENT_WORK,29);
  assert.equal(DOCUMENT_WORK_PREFIX,56);assert.equal(DOCUMENT_BEGIN_BYTES,16);assert.equal(DOCUMENT_RESULT_PREFIX,40);
  assert.equal(MAX_SERVICE,1048576);assert.equal(MAX_DOCUMENT_RESULT,1048616);
  const body=new Uint8Array(1048616),raw=encodeRecord(28,documentIdentity,body,{transfer:commandTransfer});
  const module=fakeModule('kernel'),endpoint=createCopiedEndpoint(module,'kernel');
  endpoint.call(28,raw,80);assert.equal(module.calls.length,1);assert.equal(module.calls[0].payload.byteLength,1048616);
  assert.throws(()=>encodeRecord(28,documentIdentity,new Uint8Array(1048617)),BridgeError);
  for(const operation of [OP.SUBMIT,OP.COMMAND_RESULT,OP.PEEK_DOCUMENT_WORK,OP.BEGIN_DOCUMENT_WORK]){
    assert.throws(()=>encodeRecord(operation,documentIdentity,body),BridgeError);
    const wrong=new Uint8Array(raw);new DataView(wrong.buffer).setUint16(6,operation,true);
    const before=module.allocations.length;assert.throws(()=>endpoint.call(operation,wrong,80),BridgeError);
    assert.equal(module.allocations.length,before,'unrelated operations must reject the large body before allocating');
  }
});
test('document query/form work is queued, claimed once and settled only after exact matching turns return',()=>{
  for(const kind of [1,2]){
    const s=documentScenario();s.start();const payload=documentWork({kind});s.queue(payload);s.bridge.poll();s.bridge.poll();
    assert.equal(s.tasks.length,1);assert.equal(s.queryCalls+s.formCalls,0);assert.equal(s.events.length,0);s.flush();
    assert.equal(s.bridge.state,'ready');assert.equal(s.queryCalls+s.formCalls,1);assert.equal(s.claims.length,1);assert.equal(s.results.length,1);
    assert.equal(s.depth,0);assert.equal(s.ackCalls,0,'transport must not synthesize action ACK work');
    const claim=s.claims[0],result=s.results[0],claimed=new DataView(claim.payload.buffer);
    assert.deepEqual(claim.identity,documentIdentity);assert.equal(claim.transfer,commandTransfer);assert.equal(claim.payload.byteLength,16);
    assert.equal(claimed.getUint32(0,true),kind);assert.equal(claimed.getUint32(4,true),0);assert.equal(claimed.getBigUint64(8,true),9007199254741101n);
    const entered=s.events.find(value=>value.role==='engine'&&value.op===(kind===1?ENGINE.QUERY:ENGINE.COMMAND));
    assert.deepEqual(entered.request.identity,documentIdentity);assert.equal(entered.request.transfer,commandTransfer);
    const native=new DataView(entered.request.payload.buffer);
    if(kind===1){assert.equal(entered.request.payload.byteLength,96);assert.equal(native.getUint32(0,true),3);assert.equal(native.getUint32(4,true),0);
      assert.equal(Buffer.from(entered.request.payload.subarray(8,40)).toString('hex'),documentSchema);assert.equal(native.getUint32(40,true),1048576);assert.equal(native.getUint32(44,true),48);}
    else assert.deepEqual(entered.request.payload,mutate(mutate(payload,0,6),4,0));
    const view=new DataView(result.payload.buffer);assert.equal(view.getUint32(0,true),kind);assert.equal(view.getUint32(4,true),0);
    assert.equal(view.getBigUint64(8,true),9007199254741101n);assert.equal(view.getInt32(16,true),0);assert.equal(view.getUint32(20,true),kind===1?0:1);
    assert.equal(view.getUint32(24,true),kind===1?48:52);assert.equal(view.getUint32(28,true),kind===1?0:1);
    assert.equal(view.getBigUint64(32,true),kind===1?9007199254741123n:0n);assert.equal(result.payload.byteLength,kind===1?88:92);
    assert.deepEqual(result.identity,documentIdentity);assert.equal(result.transfer,commandTransfer);
    const operations=s.events.map(value=>[value.role,value.op]);
    assert.ok(operations.findIndex(value=>value[0]==='kernel'&&value[1]===29)<operations.findIndex(value=>value[0]==='engine'&&value[1]===(kind===1?5:4)));
    assert.equal(s.events.filter(value=>value.role==='kernel'&&value.op===OP.TURN_ENTER).length,1);
    assert.equal(s.events.filter(value=>value.role==='kernel'&&value.op===OP.TURN_LEAVE).length,1);
    assert.ok(operations.findIndex(value=>value[0]==='kernel'&&value[1]===OP.TURN_LEAVE)<operations.findIndex(value=>value[0]==='kernel'&&value[1]===28));
    s.bridge.poll();s.flush();assert.equal(s.queryCalls+s.formCalls,1);assert.equal(s.results.length,1);assert.deepEqual(s.failures,[]);
  }
});
test('document full query/form replies are reserved before BEGIN and copied through growth and free',()=>{
  for(const kind of [1,2]){
    const s=documentScenario();s.start();const packet=documentPacket(kind===1?4:5,{length:1048576});packet[packet.length-1]=231;
    let outputPointer,outputCapacity;
    if(kind===1)s.hooks.query=()=>queryResult({packet});else s.hooks.form=()=>documentCommandResult({packet});
    s.hooks.kernel=(op,request)=>{if(op===OP.BEGIN_DOCUMENT_WORK){
      const allocations=s.engineModule.allocations.slice(-2);
      assert.equal(allocations[0].length,kind===1?1048672:1048680,'complete output must be allocated before claiming effects');
      outputPointer=allocations[0].pointer;outputCapacity=allocations[0].length;
      assert.equal(allocations[1].length,HEADER_BYTES+(kind===1?96:137));
      const input=s.engineModule.HEAPU8.subarray(allocations[1].pointer,allocations[1].pointer+allocations[1].length);
      const prepared=decodeRecord(input,{kind:kind===1?ENGINE.QUERY:ENGINE.COMMAND,receipt:false,maximum:input.byteLength});
      assert.deepEqual(prepared.payload.subarray(kind===1?48:56),documentPacket(kind),'owned input copy must precede the claim');
      assert.equal(s.queryCalls+s.formCalls,0);
    }};
    s.engineModule.onAllocate=()=>s.engineModule.instance.exports.memory.grow(1);
    const entered=kind===1?ENGINE.QUERY:ENGINE.COMMAND;
    s.hooks.providerReceipt=(op,request,payload)=>{
      assert.equal(op,entered);const result=receipt(request,{payload});s.engineModule.instance.exports.memory.grow(1);
      s.engineModule.onFree=()=>{
        assert.ok(outputPointer>0);s.engineModule.HEAPU8.fill(0,outputPointer,outputPointer+outputCapacity);
        packet.fill(0);s.engineModule.instance.exports.memory.grow(1);
      };return result;
    };
    s.queue(documentWork({kind}));s.bridge.poll();s.flush();
    assert.equal(s.bridge.state,'ready');assert.equal(s.results.length,1);assert.equal(s.results[0].payload.byteLength,1048616);
    assert.equal(new DataView(s.results[0].payload.buffer).getUint32(24,true),1048576);
    assert.equal(s.results[0].payload.at(-1),231,'completion must own bytes before engine free mutates caller storage');
    assert.deepEqual(s.failures,[]);
  }
});
test('document ACK7 forwards retired/already/stale bytes with final MAX sequence and no Host callback or ACK-of-ACK',()=>{
  for(const code of [0,1,2]){
    const s=documentScenario();s.start();const work=documentWork({kind:3,sequence:U64_MAX,payload:scalar64(U64_MAX-1n)});
    const packet=actionAckResult(U64_MAX-1n,code);
    s.hooks.ack=request=>documentCommandResult({sequence:new DataView(request.payload.buffer).getBigUint64(8,true),handled:0,packet});
    s.queue(work);s.bridge.poll();s.flush();
    assert.equal(s.bridge.state,'ready');assert.equal(s.ackCalls,1);assert.equal(s.formCalls+s.queryCalls,0);
    assert.equal(s.claims.length,1);assert.equal(s.results.length,1);assert.equal(s.results[0].payload.byteLength,56);
    assert.deepEqual(s.results[0].payload.subarray(40),packet);assert.equal(new DataView(s.results[0].payload.buffer).getBigUint64(8,true),U64_MAX);
    assert.equal(s.events.some(value=>value.role==='kernel'&&[OP.TURN_ENTER,OP.TURN_LEAVE,OP.SUBMIT].includes(value.op)),false);
    const native=s.events.find(value=>value.role==='engine'&&value.op===ENGINE.COMMAND);
    assert.equal(native.cap,120);assert.deepEqual(native.request.payload,mutate(mutate(work,0,7),4,0));
    s.bridge.poll();s.flush();assert.equal(s.ackCalls,1);assert.equal(s.results.length,1);
  }
});
test('closed document cleanup still claims and settles old full-identity ACK work after PUMP becomes stale',()=>{
  const s=documentScenario();s.start();closeCurrentDocument(s);
  s.queue(documentWork({kind:3,sequence:U64_MAX,payload:scalar64(U64_MAX-1n)}));s.bridge.poll();s.flush();
  assert.equal(s.bridge.state,'ready');assert.equal(s.ackCalls,1);assert.equal(s.queryCalls+s.formCalls,0);
  assert.equal(s.claims.length,1);assert.equal(s.results.length,1);assert.equal(s.work.length,0);
  for(const request of [...s.claims,...s.results]){
    assert.deepEqual(request.identity,documentIdentity);assert.equal(request.transfer,commandTransfer);assert.equal(request.source,0);
    assert.equal(new DataView(request.payload.buffer).getBigUint64(8,true),U64_MAX);
  }
  assert.deepEqual(s.results[0].payload.subarray(40),actionAckResult(U64_MAX-1n));
  const scheduler=s.events.filter(value=>value.role==='kernel'&&[OP.PUMP_ONE,OP.PEEK_DOCUMENT_WORK].includes(value.op));
  assert.ok(scheduler.some(value=>value.op===OP.PUMP_ONE));assert.ok(scheduler.some(value=>value.op===OP.PEEK_DOCUMENT_WORK));
  for(const value of scheduler)assert.deepEqual(value.request.identity,documentIdentity,'closed scheduling must retain the actual old target');
  const native=s.events.find(value=>value.role==='engine'&&value.op===ENGINE.COMMAND);
  assert.deepEqual(native.request.identity,documentIdentity);assert.equal(native.request.transfer,commandTransfer);
  assert.equal(s.events.some(value=>value.role==='kernel'&&[OP.TURN_ENTER,OP.TURN_LEAVE,OP.BEGIN_DOCUMENT].includes(value.op)),false);
  assert.equal(s.events.some(value=>value.role==='engine'&&value.op===ENGINE.ADVANCE),false);
  assert.deepEqual(s.bridge.identity,{...documentIdentity,document:0n,generation:0n});
  const exports=s.engineModule.exports.length;s.bridge.poll();s.flush();
  assert.equal(s.engineModule.exports.length,exports);assert.equal(s.ackCalls,1);assert.equal(s.results.length,1);assert.deepEqual(s.failures,[]);
});
test('closed document EMPTY barrier retains requested advance until an exact idle receipt arrives',()=>{
  const s=documentScenario();s.start();closeCurrentDocument(s);let service=2;
  s.hooks.kernel=(op,request)=>{
    if(op===OP.PUMP_ONE)return receipt(request,{control:CONTROL.STALE});
    if(op===OP.PEEK_DOCUMENT_WORK)return receipt(request,{control:CONTROL.EMPTY,service});
  };
  assert.equal(s.bridge.advance(),true);s.flush();
  assert.equal(s.bridge.state,'ready');assert.equal(s.events.some(value=>value.role==='engine'&&value.op===ENGINE.ADVANCE),false);
  assert.equal(s.claims.length+s.results.length,0);assert.equal(s.queryCalls+s.formCalls+s.ackCalls,0);
  assert.equal(s.tasks.length,0,'a pending barrier must not spin the scheduler');
  service=0;s.bridge.poll();s.flush();
  const advances=s.events.filter(value=>value.role==='engine'&&value.op===ENGINE.ADVANCE);
  assert.equal(advances.length,1);assert.deepEqual(advances[0].request.identity,{...documentIdentity,document:0n,generation:0n});
  for(const value of s.events.filter(value=>value.role==='kernel'&&[OP.PUMP_ONE,OP.PEEK_DOCUMENT_WORK].includes(value.op)))
    assert.deepEqual(value.request.identity,documentIdentity);
  assert.equal(s.events.some(value=>value.role==='kernel'&&value.op===OP.BEGIN_DOCUMENT),false);
  s.bridge.poll();s.flush();assert.equal(s.events.filter(value=>value.role==='engine'&&value.op===ENGINE.ADVANCE).length,1);
  assert.deepEqual(s.failures,[]);
});
test('closed document malformed EMPTY status or receipt authority stops before generic advance',()=>{
  for(const patch of [{service:1},{service:14},{identity:nextIdentity},
    {identity:{...documentIdentity,document:0n,generation:0n}},{transfer:commandTransfer},{source:1},{payload:scalar32(0)}]){
    const s=documentScenario();s.start();closeCurrentDocument(s);
    s.hooks.kernel=(op,request)=>{
      if(op===OP.PUMP_ONE)return receipt(request,{control:CONTROL.STALE});
      if(op===OP.PEEK_DOCUMENT_WORK)return receipt(request,{control:CONTROL.EMPTY,...patch});
    };
    s.bridge.advance();s.flush();assert.equal(s.bridge.state,'failed');
    assert.equal(s.events.some(value=>value.role==='engine'&&value.op===ENGINE.ADVANCE),false);
    assert.equal(s.claims.length+s.results.length,0);assert.equal(s.queryCalls+s.formCalls+s.ackCalls,0);
    const kernelExports=s.kernelModule.exports.length,engineExports=s.engineModule.exports.length;s.bridge.poll();s.flush();
    assert.equal(s.kernelModule.exports.length,kernelExports);assert.equal(s.engineModule.exports.length,engineExports);
  }
});
test('any Host callback during ACK7 is terminal and cannot manufacture a result or cleanup proof',()=>{
  for(const operation of [OP.TURN_ENTER,HOST.WAKE]){
    const s=documentScenario();s.start();s.hooks.ack=request=>{
      s.native(operation,new Uint8Array(),request.identity,request.transfer);
      return documentCommandResult({handled:0,packet:actionAckResult(9007199254741100n)});
    };
    const freed=s.engineModule.freed.length;s.queue(documentWork({kind:3}));s.bridge.poll();s.flush();
    assert.equal(s.bridge.state,'failed');assert.equal(s.ackCalls,1);assert.equal(s.results.length,0);assert.equal(s.engine.poisoned,true);
    assert.equal(s.engineModule.freed.length,freed);const exports=s.engineModule.exports.length;s.bridge.poll();s.flush();
    assert.equal(s.engineModule.exports.length,exports);
  }
});
test('document allocation refusal and BEGIN claim refusal stop before provider entry',()=>{
  for(const failAt of [1,2]){
    const s=documentScenario();s.start();let attempts=0;const allocate=s.engineModule._malloc;
    s.engineModule._malloc=length=>++attempts===failAt?0:allocate(length);
    s.queue();s.bridge.poll();s.flush();assert.equal(s.bridge.state,'failed');assert.equal(s.queryCalls,0);
    assert.equal(s.claims.length,0);assert.equal(s.results.length,0);
  }
  for(const patch of [{control:CONTROL.STALE},{service:2},{source:1},{transfer:commandTransfer+1n},{identity:nextIdentity},{payload:scalar32(1)}]){
    const s=documentScenario();s.start();let claims=0;s.hooks.kernel=(op,request)=>{if(op===OP.BEGIN_DOCUMENT_WORK){++claims;return receipt(request,patch);}};
    s.queue();s.bridge.poll();s.flush();assert.equal(s.bridge.state,'failed');assert.equal(s.queryCalls,0);assert.equal(claims,1);assert.equal(s.results.length,0);
  }
});
test('malformed document mailbox catalog, shallow NDV2 join and authority reject before BEGIN or effects',()=>{
  const valid=documentWork(),bad=[valid.subarray(0,55),mutate(valid,0,0),mutate(valid,0,4),mutate(valid,4,1),mutate(valid,8,0n,8),
    mutate(valid,8,U64_MAX,8),mutate(valid,16,0),mutate(valid,48,1048575),mutate(valid,48,1048577),mutate(valid,52,47),
    documentWork({payload:new Uint8Array(47)}),documentWork({payload:new Uint8Array(49)}),
    documentWork({kind:2,payload:new Uint8Array(80)}),documentWork({kind:2,payload:new Uint8Array(6247)}),
    documentWork({kind:3,payload:new Uint8Array(7)}),documentWork({kind:3,payload:new Uint8Array(9)}),
    documentWork({kind:3,payload:scalar64(0n)}),documentWork({kind:3,payload:scalar64(U64_MAX)}),
    documentWork({kind:3,payload:scalar64(9007199254741101n)})];
  for(const [offset,value,width]of [[56,0,4],[60,1,4],[64,documentIdentity.instance+1n,8],
    [72,documentIdentity.document,8],[80,documentIdentity.generation,8],[88,1n,8],[96,0n,8]])bad.push(mutate(valid,offset,value,width));
  const form=documentWork({kind:2});bad.push(mutate(form,96,1n,8));
  for(const payload of bad){const s=documentScenario();s.start();s.queue(payload);s.bridge.poll();s.flush();
    assert.equal(s.bridge.state,'failed');assert.equal(s.queryCalls+s.formCalls+s.ackCalls,0);assert.equal(s.claims.length,0);assert.equal(s.results.length,0);}
  for(const patch of [{source:1},{source:2},{transfer:0n},{identity:{...documentIdentity,instance:0n}},
    {identity:{...documentIdentity,document:0n}},{identity:{...documentIdentity,generation:0n}},{identity:nextIdentity}]){
    const s=documentScenario();s.start();s.queue(valid,patch);s.bridge.poll();s.flush();assert.equal(s.bridge.state,'failed');
    assert.equal(s.queryCalls+s.formCalls+s.ackCalls,0);assert.equal(s.claims.length,0);
  }
});
test('document known pre-entry query/form rejections need no TURN and never retry effects',()=>{
  for(const kind of [1,2,3]){
    const s=documentScenario();s.start();
    s.hooks.engine=(op,request)=>{
      if(op!==(kind===1?ENGINE.QUERY:ENGINE.COMMAND))return;
      const payload=kind===1?queryResult({status:-5,revision:0n,packet:new Uint8Array()}):
        documentCommandResult({sequence:new DataView(request.payload.buffer).getBigUint64(8,true),status:-5,disposition:0,handled:0,packet:new Uint8Array()});
      return receipt(request,{payload});
    };
    s.queue(documentWork({kind}));s.bridge.poll();s.flush();assert.equal(s.bridge.state,'ready');assert.equal(s.results.length,1);
    const view=new DataView(s.results[0].payload.buffer);assert.equal(view.getInt32(16,true),-5);assert.equal(view.getUint32(20,true),0);
    assert.equal(view.getUint32(24,true),0);assert.equal(view.getUint32(28,true),0);assert.equal(s.results[0].payload.byteLength,40);
    assert.equal(s.events.some(value=>value.role==='kernel'&&value.op===OP.TURN_ENTER),false);
    const calls=s.engineModule.calls.length;s.bridge.poll();s.flush();assert.equal(s.engineModule.calls.length,calls);
  }
});
test('malformed document native results and shallow reply joins poison without inventing an outcome',()=>{
  const query=queryResult(),form=documentCommandResult();
  const invalidQueries=[query.subarray(0,15),queryResult({status:1}),queryResult({status:-9}),queryResult({revision:0n}),queryResult({written:49}),
    queryResult({status:-8,revision:0n,packet:new Uint8Array([1])}),queryResult({status:-8,revision:1n,packet:new Uint8Array()}),
    mutate(query,16,0),mutate(query,22,5,2),mutate(query,24,documentIdentity.instance+1n,8),
    mutate(query,32,documentIdentity.document,8),mutate(query,40,documentIdentity.generation,8),mutate(query,48,1n,8),mutate(query,56,1n,8)];
  const invalidForms=[form.subarray(0,23),documentCommandResult({status:1}),documentCommandResult({status:-9}),documentCommandResult({disposition:0}),
    documentCommandResult({disposition:2,handled:2}),documentCommandResult({disposition:3}),documentCommandResult({handled:2}),documentCommandResult({written:53}),
    documentCommandResult({status:-5,disposition:0,handled:0,packet:new Uint8Array([1])}),
    documentCommandResult({status:-5,disposition:0,handled:1,packet:new Uint8Array()}),
    documentCommandResult({sequence:9007199254741102n}),documentCommandResult({status:-1,handled:0,packet:new Uint8Array()}),
    mutate(form,24,0),mutate(form,30,4,2),mutate(form,56,1n,8),mutate(form,64,1n,8)];
  for(const [kind,values]of [[1,invalidQueries],[2,invalidForms]])for(const result of values){
    const s=documentScenario();s.start();if(kind===1)s.hooks.query=()=>result;else s.hooks.form=()=>result;
    s.queue(documentWork({kind}));s.bridge.poll();s.flush();assert.equal(s.bridge.state,'failed');assert.equal(s.queryCalls+s.formCalls,1);
    assert.equal(s.results.length,0);assert.equal(s.engine.poisoned,true);const exports=s.engineModule.exports.length;s.bridge.poll();s.flush();assert.equal(s.engineModule.exports.length,exports);
  }
  for(const packet of [new Uint8Array(15),new Uint8Array(17),actionAckResult(1n),actionAckResult(9007199254741100n,3),
    mutate(actionAckResult(9007199254741100n),12,1)]){
    const s=documentScenario();s.start();s.hooks.ack=()=>documentCommandResult({handled:0,packet});
    s.queue(documentWork({kind:3}));s.bridge.poll();s.flush();assert.equal(s.bridge.state,'failed');assert.equal(s.ackCalls,1);assert.equal(s.results.length,0);
  }
});
test('document result receipts and collection receipts preserve every original identity and status field',()=>{
  for(const patch of [{source:1},{identity:nextIdentity},{identity:{...documentIdentity,worker:1n}},
    {transfer:commandTransfer+1n},{control:CONTROL.STALE},{service:1}]){
    const s=documentScenario();s.start();s.hooks.providerReceipt=(op,request,payload)=>receipt(request,{payload,...patch});
    s.queue();s.bridge.poll();s.flush();assert.equal(s.bridge.state,'failed');assert.equal(s.queryCalls,1);assert.equal(s.results.length,0);
  }
  for(const patch of [{control:CONTROL.STALE},{service:2},{source:1},{identity:nextIdentity},{transfer:commandTransfer+1n},{payload:scalar32(1)}]){
    const s=documentScenario();s.start();let collections=0;
    s.hooks.kernel=(op,request)=>{if(op===OP.DOCUMENT_WORK_RESULT){++collections;return receipt(request,patch);}};
    s.queue();s.bridge.poll();s.flush();assert.equal(s.bridge.state,'failed');assert.equal(s.queryCalls,1);assert.equal(collections,1);
    const calls=s.engineModule.calls.length;s.bridge.poll();s.flush();assert.equal(s.engineModule.calls.length,calls);assert.equal(collections,1);
  }
});
test('naturally completed uncertain document turns settle once and forbid free, further exports and effect replay',()=>{
  for(const [kind,status,disposition]of [[1,-8,0],[2,-1,2],[2,-8,0],[2,-8,2]]){
    const s=documentScenario();s.start();
    if(kind===1)s.hooks.query=()=>queryResult({status,revision:0n,packet:new Uint8Array()});
    else s.hooks.form=()=>documentCommandResult({status,disposition,handled:0,packet:new Uint8Array()});
    const freed=s.engineModule.freed.length;s.queue(documentWork({kind}));s.bridge.poll();s.flush();
    assert.equal(s.bridge.state,'failed');assert.equal(s.results.length,1);assert.equal(s.queryCalls+s.formCalls,1);
    assert.equal(s.engineModule.freed.length,freed);assert.equal(s.engine.poisoned,true);
    const view=new DataView(s.results[0].payload.buffer);assert.equal(view.getInt32(16,true),status);assert.equal(view.getUint32(20,true),disposition);
    assert.equal(s.events.filter(value=>value.role==='kernel'&&value.op===OP.TURN_ENTER).length,1);
    assert.equal(s.events.filter(value=>value.role==='kernel'&&value.op===OP.TURN_LEAVE).length,1);
    const exports=s.engineModule.exports.length;s.bridge.poll();s.flush();assert.equal(s.engineModule.exports.length,exports);assert.equal(s.results.length,1);
  }
  const ack=documentScenario();ack.start();ack.hooks.ack=()=>documentCommandResult({status:-8,disposition:2,handled:0,packet:new Uint8Array()});
  const freed=ack.engineModule.freed.length;
  ack.queue(documentWork({kind:3}));ack.bridge.poll();ack.flush();
  assert.equal(ack.bridge.state,'failed');assert.equal(ack.results.length,1,'returned callback-free ACK must retain its uncertain evidence');
  assert.equal(ack.ackCalls,1);assert.equal(ack.engine.poisoned,true);assert.equal(ack.engineModule.freed.length,freed);
  const expected=new Uint8Array(40),view=new DataView(expected.buffer);
  view.setUint32(0,3,true);view.setBigUint64(8,9007199254741101n,true);view.setInt32(16,-8,true);view.setUint32(20,2,true);
  assert.deepEqual(ack.results[0].payload,expected);assert.deepEqual(ack.results[0].identity,documentIdentity);assert.equal(ack.results[0].transfer,commandTransfer);
  assert.equal(ack.events.some(value=>value.role==='kernel'&&[OP.TURN_ENTER,OP.TURN_LEAVE].includes(value.op)),false);
  const exports=ack.engineModule.exports.length;ack.bridge.poll();ack.flush();
  assert.equal(ack.engineModule.exports.length,exports);assert.equal(ack.results.length,1);
});
test('uncertain form and callback-free ACK results retain bounded opaque bytes and handled exactly once',()=>{
  const cases=[
    {kind:2,status:0,handled:1,packet:documentPacket(5)},
    {kind:2,status:0,handled:0,packet:new Uint8Array()},
    {kind:2,status:-8,handled:1,packet:new Uint8Array([255,0,222])},
    {kind:2,status:-8,handled:0,packet:new Uint8Array(1048576).fill(229)},
    {kind:3,status:0,handled:1,packet:new Uint8Array(16).fill(255)},
    {kind:3,status:0,handled:0,packet:new Uint8Array()},
    {kind:3,status:-8,handled:0,packet:new Uint8Array([255])},
    {kind:3,status:-8,handled:1,packet:new Uint8Array(16)}
  ];
  for(const {kind,status,handled,packet}of cases){
    const s=documentScenario();s.start();const sequence=kind===3?U64_MAX:9007199254741101n;
    const returned=documentCommandResult({sequence,status,disposition:2,handled,packet});
    if(kind===2)s.hooks.form=()=>returned;else s.hooks.ack=()=>returned;
    const freed=s.engineModule.freed.length;
    s.queue(documentWork({kind,sequence,...(kind===3?{payload:scalar64(U64_MAX-1n)}:{})}));s.bridge.poll();s.flush();
    assert.equal(s.bridge.state,'failed');assert.equal(s.engine.poisoned,true);assert.equal(s.engineModule.freed.length,freed);
    assert.equal(s.claims.length,1);assert.equal(s.results.length,1);assert.equal(s.work.length,0);
    assert.equal(s.formCalls,kind===2?1:0);assert.equal(s.ackCalls,kind===3?1:0);assert.equal(s.queryCalls,0);
    const expected=new Uint8Array(40+packet.byteLength),view=new DataView(expected.buffer);
    view.setUint32(0,kind,true);view.setBigUint64(8,sequence,true);view.setInt32(16,status,true);view.setUint32(20,2,true);
    view.setUint32(24,packet.byteLength,true);view.setUint32(28,handled,true);expected.set(packet,40);
    assert.deepEqual(s.results[0].payload,expected,'opaque evidence must retain every Owner prefix field and byte');
    assert.deepEqual(s.results[0].identity,documentIdentity);assert.equal(s.results[0].transfer,commandTransfer);assert.equal(s.results[0].source,0);
    for(const operation of [OP.TURN_ENTER,OP.TURN_LEAVE])
      assert.equal(s.events.filter(value=>value.role==='kernel'&&value.op===operation).length,kind===2?1:0);
    assert.equal(s.events.filter(value=>value.role==='kernel'&&value.op===OP.DOCUMENT_WORK_RESULT).length,1);
    const engineExports=s.engineModule.exports.length,kernelExports=s.kernelModule.exports.length;
    assert.equal(s.bridge.advance(),false);s.bridge.poll();s.flush();
    assert.equal(s.engineModule.exports.length,engineExports);assert.equal(s.kernelModule.exports.length,kernelExports);
    assert.equal(s.results.length,1);assert.equal(s.ackCalls,kind===3?1:0,'unknown form evidence must not stage action ACK cleanup');
  }
});
test('uncertain document evidence still rejects malformed counts, capacity, status, handled and sequence before result28',()=>{
  for(const kind of [2,3]){
    const base={status:-8,disposition:2,handled:1,packet:new Uint8Array([253])};
    const invalid=[{written:2},{packet:new Uint8Array((kind===2?1048576:16)+1)},
      {handled:2},{status:1},{status:-9},{sequence:9007199254741102n}];
    for(const patch of invalid){
      const s=documentScenario();s.start();const returned=documentCommandResult({...base,...patch});
      if(kind===2)s.hooks.form=()=>returned;else s.hooks.ack=()=>returned;
      const freed=s.engineModule.freed.length;s.queue(documentWork({kind}));s.bridge.poll();s.flush();
      assert.equal(s.bridge.state,'failed');assert.equal(s.engine.poisoned,true);assert.equal(s.results.length,0);
      assert.equal(s.claims.length,1);assert.equal(s.formCalls+s.ackCalls,1);assert.equal(s.engineModule.freed.length,freed);
      const exports=s.engineModule.exports.length;s.bridge.poll();s.flush();assert.equal(s.engineModule.exports.length,exports);
    }
  }
});
test('opaque uncertain form bytes cannot settle without exactly one complete matching native turn',()=>{
  for(const mode of ['missing','unbalanced','wrong-transfer','duplicate']){
    const s=documentScenario();s.start();s.hooks.engine=(op,request)=>{
      if(op!==ENGINE.COMMAND)return;
      if(mode==='unbalanced')s.native(OP.TURN_ENTER,new Uint8Array(),request.identity,request.transfer);
      if(mode==='wrong-transfer')s.native(OP.TURN_ENTER,new Uint8Array(),request.identity,request.transfer+1n);
      if(mode==='duplicate'){s.guarded(request,()=>{});s.guarded(request,()=>{});}
      return receipt(request,{payload:documentCommandResult({status:0,disposition:2,handled:1,packet:new Uint8Array([255])})});
    };
    const freed=s.engineModule.freed.length;s.queue(documentWork({kind:2}));s.bridge.poll();s.flush();
    assert.equal(s.bridge.state,'failed');assert.equal(s.engine.poisoned,true);assert.equal(s.results.length,0);assert.equal(s.claims.length,1);
    assert.equal(s.events.filter(value=>value.role==='engine'&&value.op===ENGINE.COMMAND).length,1);
    assert.equal(s.engineModule.freed.length,freed);assert.equal(s.ackCalls,0);
    const exports=s.engineModule.exports.length;s.bridge.poll();s.flush();assert.equal(s.engineModule.exports.length,exports);
  }
});
test('document traps, unbalanced or duplicate turns and cleanup failure never fabricate result28',()=>{
  for(const mode of ['trap','missing','unbalanced','wrong-transfer','duplicate','free']){
    const s=documentScenario();s.start();const freed=s.engineModule.freed.length;
    if(mode==='free')s.hooks.providerReceipt=(op,request,payload)=>{s.engineModule.onFree=()=>{throw Error('document free trap');};return receipt(request,{payload});};
    else s.hooks.engine=(op,request)=>{
      if(op!==ENGINE.QUERY)return;
      if(mode==='trap')throw Error('document export trap');
      if(mode==='unbalanced')s.native(OP.TURN_ENTER,new Uint8Array(),request.identity,request.transfer);
      if(mode==='wrong-transfer')s.native(OP.TURN_ENTER,new Uint8Array(),request.identity,request.transfer+1n);
      if(mode==='duplicate'){s.guarded(request,()=>{});s.guarded(request,()=>{});}
      return receipt(request,{payload:queryResult()});
    };
    s.queue();s.bridge.poll();s.flush();assert.equal(s.bridge.state,'failed');assert.equal(s.results.length,0);assert.equal(s.engine.poisoned,true);
    assert.equal(s.engineModule.freed.length,freed+(mode==='free'?1:0));
    const exports=s.engineModule.exports.length;s.bridge.poll();s.flush();assert.equal(s.engineModule.exports.length,exports);
  }
});
test('document allocator Host callbacks cannot be ignored to reach a second allocation, claim or provider export',()=>{
  for(const operation of [OP.TURN_ENTER,HOST.WAKE]){
    const s=documentScenario();s.start();const callback=documentCallbackScratch(s,operation),allocate=s.engineModule._malloc;
    const exports=s.engineModule.exports.length,freed=s.engineModule.freed.length;let attempts=0;
    s.engineModule._malloc=length=>{++attempts;assert.equal(callback(),-4);return allocate(length);};
    s.queue();s.bridge.poll();s.flush();
    assert.equal(s.bridge.state,'failed');assert.equal(s.engine.poisoned,true);assert.equal(attempts,1);
    assert.deepEqual(s.engineModule.exports.slice(exports),['malloc'],'poisoned allocator must be the last interpreter export');
    assert.equal(s.engineModule.freed.length,freed);assert.equal(s.claims.length,0);assert.equal(s.results.length,0);
    assert.equal(s.queryCalls+s.formCalls+s.ackCalls,0);
    const stopped=s.engineModule.exports.length;s.bridge.poll();s.flush();assert.equal(s.engineModule.exports.length,stopped);
  }
});
test('document free Host callbacks cannot be ignored to reach another free or result settlement',()=>{
  for(const operation of [OP.TURN_ENTER,HOST.WAKE]){
    const s=documentScenario();s.start();const callback=documentCallbackScratch(s,operation),freed=s.engineModule.freed.length;let attempts=0;
    s.engineModule.onFree=()=>{++attempts;assert.equal(callback(),-4);};
    s.queue();s.bridge.poll();s.flush();
    assert.equal(s.bridge.state,'failed');assert.equal(s.engine.poisoned,true);assert.equal(attempts,1);
    assert.equal(s.engineModule.freed.length,freed+1);assert.equal(s.queryCalls,1);assert.equal(s.claims.length,1);assert.equal(s.results.length,0);
    assert.equal(s.ackCalls,0);const exports=s.engineModule.exports.length;s.bridge.poll();s.flush();
    assert.equal(s.engineModule.exports.length,exports,'cleanup callback failure must not replay effects or issue another export');
  }
});
test('a claimed document BEGIN dispatch/free trap forbids provider entry and every engine cleanup export',()=>{
  for(const mode of ['dispatch','free']){
    const s=documentScenario();s.start();const engineFreed=s.engineModule.freed.length;let kernelFreedAtClaim;
    s.hooks.kernel=(op,request)=>{
      if(op!==OP.BEGIN_DOCUMENT_WORK)return;
      kernelFreedAtClaim=s.kernelModule.freed.length;
      if(mode==='dispatch'){s.claims.push(request);throw Error('kernel trap after document claim');}
      s.kernelModule.onFree=()=>{throw Error('kernel free trap after document claim');};
    };
    s.queue();s.bridge.poll();s.flush();
    assert.equal(s.bridge.state,'failed');assert.equal(s.kernel.poisoned,true);assert.equal(s.engine.poisoned,true);
    assert.equal(s.claims.length,1);assert.equal(s.queryCalls+s.formCalls+s.ackCalls,0);assert.equal(s.results.length,0);
    assert.equal(s.engineModule.freed.length,engineFreed);
    assert.equal(s.kernelModule.freed.length,kernelFreedAtClaim+(mode==='free'?1:0));
    const kernelExports=s.kernelModule.exports.length,engineExports=s.engineModule.exports.length;s.bridge.poll();s.flush();
    assert.equal(s.kernelModule.exports.length,kernelExports);assert.equal(s.engineModule.exports.length,engineExports);
  }
});
test('document copies preserve the original target, transfer and packet through navigation and source mutation',()=>{
  const s=documentScenario();s.start();const payload=documentWork(),original=new Uint8Array(payload);
  s.hooks.query=request=>{
    payload.fill(0);
    s.native(OP.CLOSE_DOCUMENT,new Uint8Array(),request.identity,request.transfer);
    s.native(OP.BEGIN_DOCUMENT,new Uint8Array(),{...nextIdentity,generation:0n},request.transfer);
    return queryResult();
  };
  s.queue(payload);s.bridge.poll();s.flush();assert.equal(s.bridge.state,'ready');assert.deepEqual(s.bridge.identity,nextIdentity);
  assert.equal(s.results.length,1);assert.deepEqual(s.results[0].identity,documentIdentity);assert.equal(s.results[0].transfer,commandTransfer);
  const native=s.events.find(value=>value.role==='engine'&&value.op===ENGINE.QUERY);
  assert.deepEqual(native.request.payload.subarray(48),original.subarray(56));
  const leave=s.events.find(value=>value.role==='kernel'&&value.op===OP.TURN_LEAVE);
  assert.deepEqual(leave.request.identity,documentIdentity);assert.equal(leave.request.transfer,commandTransfer);assert.deepEqual(s.failures,[]);
});
test('new document and physical lanes share one nonwrapping sequence domain while legacy MAX remains valid',()=>{
  const first=9007199254741201n;
  for(const documentFirst of [false,true]){
    const s=documentScenario({physical:true});s.start();
    if(documentFirst)s.queue(documentWork({kind:2,sequence:first}));else s.queuePhysical(command({sequence:first}));
    s.bridge.poll();s.flush();assert.equal(s.bridge.state,'ready');
    if(documentFirst)s.queuePhysical(command({sequence:first-1n}));else s.queue(documentWork({kind:2,sequence:first-1n}));
    s.bridge.poll();s.flush();assert.equal(s.bridge.state,'failed');assert.equal(s.formCalls+s.physicalCalls,1);
  }
  for(const kind of [1,2]){const s=documentScenario();s.start();s.queue(documentWork({kind,sequence:U64_MAX}));s.bridge.poll();s.flush();
    assert.equal(s.bridge.state,'failed');assert.equal(s.queryCalls+s.formCalls,0);}
  const physical=documentScenario({physical:true});physical.start();physical.queuePhysical(command({sequence:U64_MAX}));physical.bridge.poll();physical.flush();
  assert.equal(physical.bridge.state,'failed');assert.equal(physical.physicalCalls,0);
  const legacy=scenario();legacy.start();legacy.queue(command({sequence:U64_MAX}));legacy.bridge.poll();legacy.flush();
  assert.equal(legacy.bridge.state,'ready');assert.equal(legacy.effects,1);
});
test('legacy259/467 never poll document27 and new1795 never polls the physical mailbox',()=>{
  for(const physical of [false,true]){const s=scenario({physical});s.start();s.bridge.poll();s.flush();
    assert.equal(s.bridge.state,'ready');assert.equal(s.events.some(value=>value.role==='kernel'&&value.op===OP.PEEK_DOCUMENT_WORK),false);}
  const s=documentScenario();s.start();s.queuePhysical();s.queue();s.bridge.poll();s.flush();
  assert.equal(s.bridge.state,'ready');assert.equal(s.queryCalls,1);assert.equal(s.physicalCalls,0);
  assert.equal(s.events.some(value=>value.role==='kernel'&&value.op===OP.PEEK_INPUT),false);
});
