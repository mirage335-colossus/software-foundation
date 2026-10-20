// Production Worker/bootstrap code with explicit allocator/factory/dispatcher
// fakes. No HTML engine, browser, portable module, compiler or SDK is executed.
// The copied bridge's detailed ABI/turn tests live in engine_kernel_bridge_test.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFile} from 'node:fs/promises';
import {createHash,webcrypto} from 'node:crypto';
import {resolveObjectURL} from 'node:buffer';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';

const workerURL=process.argv[2]?pathToFileURL(resolve(process.argv[2])):new URL('../host/appended_engine_wasm_worker.mjs',import.meta.url);
const bootstrapURL=process.argv[3]?pathToFileURL(resolve(process.argv[3])):new URL('../host/appended_engine_browser_bootstrap.mjs',import.meta.url);
const bridgeURL=new URL('./engine_kernel_bridge.mjs',workerURL);
const {installAppendedEngineWasmWorker}=await import(workerURL.href);
const {BRIDGE_VERSION,OP,ENGINE,CONTROL,HOST,HEADER_BYTES,RECEIPT_BYTES,encodeRecord,decodeRecord}=await import(bridgeURL.href);
if(!globalThis.crypto)Object.defineProperty(globalThis,'crypto',{value:webcrypto,configurable:true});
const encoder=new TextEncoder(),decoder=new TextDecoder(),U64_MAX=(1n<<64n)-1n;
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const profile=()=>({schema_version:1,kind:'foundation-copied-engine-v1',target:'browser-wasm32',
  binding:'copied-owner-bridge/direct-worker-v1',pointer_bits:32,pthread:false,shared_memory:false,
  bridge_abi:BRIDGE_VERSION,capabilities:'259',contract_sha256:'1'.repeat(64),
  build_sha256:'2'.repeat(64),source_recipe_sha256:'3'.repeat(64)});
const physicalProfile=()=>({...profile(),kind:'foundation-copied-engine-physical-v1',
  binding:'copied-owner-bridge/direct-worker-physical-v1',capabilities:'467',command_catalog_sha256:'d244e6a17561b49b937ad25058f2d662f4f86063633b716bdb87d0250796a47b',
  surface_protocol_version:1,surface_capabilities:'8225',mouse_input_version:1,key_mapping_version:1,
  viewport_width:800,viewport_height:600,display_scale:1});
const documentProfile=(physical=false)=>({...profile(),kind:'foundation-copied-engine-document-v2',
  binding:'copied-owner-bridge/direct-worker-document-v2',capabilities:physical?'2003':'1795',
  provider_abi_major:1,provider_abi_minor:1,host_abi_major:1,host_abi_minor:0,
  document_profile:physical?'foundation-engine-copied2003-ndv2-v1':'foundation-engine-copied1795-ndv2-v1',
  contract_sha256:'aba7800e6aab1898f3614f0b1ac53e59b9f622bf1e9d3a413f50d672a3662298',
  base_header_sha256:'a8e89da85d34b29a4d1bc454495791fa604b81e3477e48ce8ca902e4333a9c0d',
  extension_header_sha256:'7b047bae4d0072ef156ea94ba637566d563fea3a95d43c4c6314afc919b1d626',
  document_catalog_sha256:'6e555d4c3bb71fbc965e1ca49671fab64d744913e18f45b9ba273505e0c6bcf5',
  document_schema_sha256:'f11fd061350f8d663dbcdec7cf0a063e4fb0ff3564d285076690f58e8a84143d',
  action_ack_schema_sha256:'1eb6c2d4f56acebc1423d9e2b5bf9a1717a99963a5c3f11f4b9d7b0fe33b50f5',viewport_width:800,viewport_height:600,
  ...(physical?{command_catalog_sha256:'d244e6a17561b49b937ad25058f2d662f4f86063633b716bdb87d0250796a47b',
    surface_protocol_version:1,surface_capabilities:'8225',mouse_input_version:1,key_mapping_version:1,display_scale:1}:{})});
const microtasks=async()=>{for(let count=0;count<12;++count)await Promise.resolve();};
const bytes=value=>new Uint8Array(value);
const profileQuery={name:'gui_web_engine_profile_v1',type:'number',kinds:[],args:[]};
const kernelWasmLookup='gui_appended_engine_wasm.wasm',defaultEngineWasmLookup='embedder.wasm';

// Independent logical Package/trailer construction using the published v1
// little-endian layout. All object properties below are in canonical order.
// The web script is inert data throughout these tests, never imported/evaluated.
function carrier(){
  const prefix=encoder.encode('<!doctype html><html><head></head><body><!--SFAPPEND01-->');
  const startup=encoder.encode('{"kind":"foundation-appended-startup","primary":"web","schema_version":1}');
  const html=encoder.encode('<!doctype html><script>globalThis.engineFixtureApplicationRan=true</script>');
  const content=Buffer.concat([startup,html]);
  const index={application:{id:'org.example.engine-fixture',name:'Engine fixture',version:'1.0.0'},
    components:{binary:{entry:null,present:false,profile:null},web:{entry:'web/index.html',present:true}},
    files:[{component:'web',length:startup.length,media_type:'application/json',offset:0,path:'web/.foundation/startup-v1.json',sha256:sha(startup)},
      {component:'web',length:html.length,media_type:'text/html',offset:startup.length,path:'web/index.html',sha256:sha(html)}],
    identities:{},kind:'foundation-appended-package',requires:{abi:{major:1,minor:0},capabilities:['foundation.startup.v1'],services:[]},schema_version:1};
  const indexBytes=encoder.encode(JSON.stringify(index)),logical=Buffer.concat([content,indexBytes]);
  const trailer=new Uint8Array(192),view=new DataView(trailer.buffer);
  trailer.set(encoder.encode('SFAPND01'));view.setUint32(8,1,true);view.setUint32(12,192,true);
  for(const [offset,value]of [[16,prefix.length],[24,logical.length],[32,content.length],[40,indexBytes.length],[48,3]])
    view.setBigUint64(offset,BigInt(value),true);
  trailer.set(Buffer.from(sha(prefix),'hex'),56);trailer.set(Buffer.from(sha(logical),'hex'),88);trailer.set(Buffer.from(sha(indexBytes),'hex'),120);
  const suffix=new Uint8Array(Buffer.concat([logical,trailer]));
  return {prefix,index,indexBytes,logical,suffix,encoded:Buffer.from(suffix).toString('base64'),packageSha256:sha(logical)};
}
const vector=carrier();

function receipt(request,{identity=request.identity,payload=new Uint8Array(),control=CONTROL.OK,service=0}={}){
  const output=new Uint8Array(RECEIPT_BYTES+payload.length),view=new DataView(output.buffer);
  output.set([70,75,66,49]);view.setUint16(4,1,true);view.setUint16(6,request.kind|0x8000,true);view.setUint32(8,output.length,true);
  for(const [index,key]of ['worker','instance','document','generation'].entries())view.setBigUint64(16+8*index,identity[key],true);
  view.setBigUint64(48,request.transfer,true);view.setUint32(56,request.source,true);view.setUint32(64,output.length-HEADER_BYTES,true);
  view.setUint32(72,control,true);view.setUint32(76,service,true);output.set(payload,RECEIPT_BYTES);return output;
}
function fakeModule(role,handler){
  let heap=new Uint8Array(4*1048576),next=128;const active=new Map(),calls=[],ccalls=[],freed=[],exports=[],allocations=[];
  const module={calls,ccalls,freed,exports,allocations,get HEAPU8(){return heap;},
    grow(){const grown=new Uint8Array(heap.length+65536);grown.set(heap);heap=grown;},
    _malloc(length){exports.push('malloc');module.onMalloc?.(length);const pointer=next;next+=Math.max(1,length)+8;
      if(next>heap.length){const grown=new Uint8Array(Math.max(next,heap.length*2));grown.set(heap);heap=grown;}
      active.set(pointer,length);allocations.push({pointer,length});return pointer;},
    _free(pointer){exports.push('free');assert.equal(active.delete(pointer),true,'free must refer to a live fake allocation');
      freed.push(pointer);module.onFree?.(pointer);if(!active.size)next=128;},
    ccall(name,type,kinds,args){ccalls.push({name,type,kinds,args});
      if(name==='gui_web_engine_profile_v1')return module._gui_web_engine_profile_v1();
      if(name==='gui_web_destroy')return;
      if(name==='gui_web_create')return JSON.stringify({epoch:args[0],ack:'0',snapshot:{title:'Engine fixture',widgets:[]}});
      if(name==='gui_web_receive')return JSON.stringify({ack:JSON.parse(args[0]).seq,snapshot:{title:'Engine fixture',widgets:[]}});
      throw Error('Unexpected fake GUI call '+name);}};
  module[role==='kernel'?'_gui_web_engine_bridge_v1':'_bib_engine_wasm_bridge_v1']=()=>{exports.push(role+'-marker');return BRIDGE_VERSION;};
  if(role==='kernel')module._gui_web_engine_profile_v1=()=>1;
  module[role==='kernel'?'_gui_web_engine_dispatch_v1':'_bib_engine_wasm_dispatch_v1']=(operation,pointer,length,output,capacity)=>{
    exports.push('dispatch');
    const raw=new Uint8Array(heap.subarray(pointer,pointer+length));
    const request=decodeRecord(raw,{kind:operation,receipt:false,maximum:raw.length});calls.push(request);
    const result=handler(operation,request,module);
    assert.ok(result.length<=capacity);heap.set(result,output);return result.length;
  };
  return module;
}
function fixture({asyncStartup=false,physicalInput=false,documentInput=null,editorInput=false,
  describedProfile=editorInput?editorProfile():documentInput?documentProfile(documentInput==='physical'):physicalInput?physicalProfile():profile(),
  engineWasmLookup=defaultEngineWasmLookup,onDirty,captureCheckpoint,beforeOwnerTask,holdFirstClose=false}={}){
  const retainedProfile=editorInput?editorProfile():documentInput?documentProfile(documentInput==='physical'):physicalInput?physicalProfile():profile();
  const posted=[],events=[],tasks=new Map(),loads=[],factoryURLs=[],ownWasmURLs=[];let nextTask=0,closed=0,hostCallback,current,closeHeld=holdFirstClose;
  const scheduler={setTimeout(task,delay){tasks.set(++nextTask,{task,delay});return nextTask;},clearTimeout(id){tasks.delete(id);}};
  const worker=U64_MAX-1n,initial={worker,instance:0n,document:0n,generation:0n};
  const document={worker,instance:U64_MAX-10n,document:U64_MAX-9n,generation:U64_MAX-8n};current={...initial};
  const kernel=fakeModule('kernel',(operation,request)=>{
    events.push(['kernel',operation]);
    if(operation===OP.CONFIGURE){
      assert.equal(new DataView(request.payload.buffer).getBigUint64(0,true),BigInt(vector.prefix.length));
      assert.equal(Buffer.from(request.payload.subarray(8,40)).toString('hex'),sha(vector.prefix));
      assert.deepEqual(request.payload.subarray(40),vector.suffix);
      return receipt(request,{payload:encoder.encode(JSON.stringify({application_name:'Engine fixture',
        entry_url:'app://'+vector.packageSha256+'/web/index.html',package_sha256:vector.packageSha256}))});
    }
    if(operation===OP.BEGIN_DOCUMENT){current={...document};return receipt(request,{identity:current});}
    if(operation===OP.BEGIN_RESOURCE_EPOCH){current={...document,generation:0n};const epoch=new Uint8Array(8);
      new DataView(epoch.buffer).setBigUint64(0,17n,true);return receipt(request,{identity:current,payload:epoch});}
    if(operation===OP.CLOSE&&closeHeld){closeHeld=false;return receipt(request,{service:2});}
    if([OP.TURN_ENTER,OP.TURN_LEAVE,OP.PUMP_ONE,OP.CLOSE].includes(operation))return receipt(request);
    // This fixture never navigates: both explicit retirement mailboxes are
    // genuinely empty, alongside the service completion/ACK mailboxes.
    if([OP.PEEK_DELIVERY,OP.PEEK_ACK_RECEIPT,OP.PEEK_RETIREMENT_AUDIT,OP.PEEK_RETIRED_DOCUMENT,OP.PEEK_INPUT,OP.PEEK_DOCUMENT_WORK,OP.PEEK_EDITOR_WORK].includes(operation))
      return receipt(request,{control:CONTROL.EMPTY});
    throw Error('Unexpected kernel fake operation '+operation);
  });
  kernel._gui_web_engine_input_describe_v1=(pointer,capacity)=>{
    assert.equal(capacity,4096);events.push(['kernel-input-describe',0]);
    const value=encoder.encode(JSON.stringify(physicalProfile()));kernel.HEAPU8.set(value,pointer);return value.length;
  };
  kernel._gui_web_engine_document_describe_v1=(pointer,capacity)=>{
    assert.equal(capacity,4096);events.push(['kernel-document-describe',0]);
    const value=encoder.encode(JSON.stringify(retainedProfile));kernel.HEAPU8.set(value,pointer);return value.length;
  };
  function callback(operation,identity){
    const request=encodeRecord(operation,identity),pointer=engine._malloc(request.length),output=engine._malloc(RECEIPT_BYTES+1048576);
    engine.HEAPU8.set(request,pointer);
    try{const length=hostCallback(operation,pointer,request.length,output,RECEIPT_BYTES+1048576);
      assert.ok(length>=RECEIPT_BYTES,'native callback must return an actual copied receipt');
      return decodeRecord(engine.HEAPU8.subarray(output,output+length),{kind:operation,worker});
    }finally{engine._free(output);engine._free(pointer);}
  }
  const engine=fakeModule('engine',(operation,request)=>{
    events.push(['engine',operation]);
    if(operation===ENGINE.DESCRIBE)return receipt(request,{payload:encoder.encode(JSON.stringify(describedProfile))});
    if(operation===ENGINE.START){
      const startup=JSON.parse(decoder.decode(request.payload));
      assert.deepEqual(startup,{raster_output:true,width:800,height:600,entry_url:'app://'+vector.packageSha256+'/web/index.html',
        package_sha256:vector.packageSha256,required_capabilities:retainedProfile.capabilities,persistence_seed:''});
      callback(OP.TURN_ENTER,request.identity);
      callback(asyncStartup?OP.BEGIN_RESOURCE_EPOCH:OP.BEGIN_DOCUMENT,{...document,generation:0n});
      callback(OP.TURN_LEAVE,request.identity);
      const payload=new Uint8Array(8);new DataView(payload.buffer).setUint32(4,2,true);
      return receipt(request,{identity:current,payload});
    }
    if(operation===ENGINE.CURRENT_DOCUMENT)return receipt(request,{identity:current,control:current.generation?CONTROL.OK:CONTROL.EMPTY});
    if(operation===ENGINE.ADVANCE)return receipt(request,{identity:current});
    throw Error('Unexpected engine fake operation '+operation);
  });
  let documentConfigured=false;
  const documentBootstrap={facts:[],configure:[],markers:[],freedAtConfigure:[]};
  if(documentInput||editorInput){
    engine._bib_engine_wasm_bridge_v1=()=>{
      const marker=documentConfigured?BRIDGE_VERSION:0;engine.exports.push('engine-marker');
      documentBootstrap.markers.push(marker);events.push(['engine-document-marker',marker]);return marker;
    };
    engine._bib_engine_wasm_document_facts_v1=(pointer,capacity)=>{
      engine.exports.push('document-facts');documentBootstrap.facts.push({pointer,capacity});events.push(['engine-document-facts',capacity]);
      assert.equal(capacity,4096);const raw=encoder.encode(JSON.stringify(retainedProfile));engine.HEAPU8.set(raw,pointer);return raw.length;
    };
    engine._bib_engine_wasm_document_configure_v1=(lo,hi)=>{
      engine.exports.push('document-configure');documentBootstrap.configure.push({lo,hi});events.push(['engine-document-configure',lo,hi]);
      documentBootstrap.freedAtConfigure.push(engine.freed.length);
      assert.equal(documentConfigured,false,'document bootstrap must configure at most once');
      assert.equal(BigInt(lo)|(BigInt(hi)<<32n),worker,'configure must preserve every Worker identity bit');
      documentConfigured=true;return 0;
    };
  }
  if(editorInput){
    kernel._gui_web_engine_editor_describe_v1=(pointer,capacity)=>{
      assert.equal(capacity,4096);events.push(['kernel-editor-describe',0]);
      const value=encoder.encode(JSON.stringify(retainedProfile));kernel.HEAPU8.set(value,pointer);return value.length;
    };
    engine._bib_engine_wasm_editor_facts_v1=engine._bib_engine_wasm_document_facts_v1;
    engine._bib_engine_wasm_editor_configure_v1=engine._bib_engine_wasm_document_configure_v1;
    delete engine._bib_engine_wasm_document_facts_v1;delete engine._bib_engine_wasm_document_configure_v1;
  }
  const ownLookup=(role,options,name=role==='kernel'?kernelWasmLookup:engineWasmLookup)=>{
    // Actual Emscripten resolves this eagerly before consulting wasmBinary.
    // Keep the factory's expected filename independent of a mutated message.
    const url=options.locateFile(name),blob=resolveObjectURL(url);
    assert.equal(new URL(url).protocol,'blob:');assert.ok(blob instanceof Blob,'own Wasm lookup must be an owned Blob');
    assert.equal(blob.type,'application/wasm');ownWasmURLs.push({role,name,url,blob});return url;
  };
  const create=role=>async options=>{
    ownLookup(role,options); // Deliberately precedes the first wasmBinary access.
    assert.ok(options.wasmBinary instanceof Uint8Array);loads.push({role,options});
    if(role==='engine')hostCallback=options.foundationEngineHost;
    return role==='kernel'?kernel:engine;
  };
  const factories={kernel:create('kernel'),engine:create('engine')};
  let factoryNumber=0;
  const scope={postMessage:value=>posted.push(value),close:()=>{++closed;}};
  const loadModule=async url=>{
    assert.equal(new URL(url).protocol,'blob:');factoryURLs.push(url);const role=factoryNumber++===0?'kernel':'engine';
    return {default:options=>factories[role](options)};
  };
  const controller=beforeOwnerTask===undefined
    ?(captureCheckpoint===undefined
      ?(onDirty===undefined?installAppendedEngineWasmWorker(scope,loadModule,scheduler):
        installAppendedEngineWasmWorker(scope,loadModule,scheduler,onDirty))
      :installAppendedEngineWasmWorker(scope,loadModule,scheduler,onDirty,captureCheckpoint))
    :installAppendedEngineWasmWorker(scope,loadModule,scheduler,onDirty,captureCheckpoint,beforeOwnerTask);
  const message={type:'init',epoch:'engine-worker-fixture',workerEpoch:String(worker),kernelProfile:'web',engineProfile:{...retainedProfile},
    kernelWasmLookup,engineWasmLookup,
    factorySource:'retained kernel factory data',wasmBinary:bytes([0,97,115,109,1,0,0,0]),
    engineFactorySource:'retained engine factory data',engineWasmBinary:bytes([0,97,115,109,1,0,0,0]),
    engineAssets:{'retained.data':bytes([7,8,9])},appendedSuffix:vector.suffix,
    prefixLength:vector.prefix.length,prefixSha256:sha(vector.prefix)};
  return {scope,controller,message,kernel,engine,posted,events,tasks,loads,factories,factoryURLs,ownWasmURLs,ownLookup,documentBootstrap,
    send:data=>scope.onmessage({data}),get closed(){return closed;},get factoryCount(){return factoryNumber;},
    step(){const found=[...tasks].find(([,item])=>item.delay===0||item.delay===1);assert.ok(found,'expected pending owner task');tasks.delete(found[0]);found[1].task();}};
}
const bootstrapSnapshot=f=>[f.kernel.exports.length,f.engine.exports.length,f.kernel.freed.length,f.engine.freed.length,
  f.kernel.ccalls.length,f.factoryCount];
async function assertBootstrapStopped(f,cutoff){
  assert.equal(f.controller.state,'failed');assert.equal(f.closed,1);
  assert.equal(f.kernel.calls.some(value=>value.kind===OP.CONFIGURE),false);
  assert.equal(f.engine.calls.length,0,'bootstrap refusal must precede DESCRIBE and START');
  assert.equal(f.kernel.ccalls.some(value=>value.name==='gui_web_create'||value.name==='gui_web_destroy'),false);
  if(cutoff)assert.deepEqual(bootstrapSnapshot(f),cutoff,'no export or cleanup may follow the injected bootstrap failure');
  const before=bootstrapSnapshot(f);
  await f.send(f.message);await f.send({type:'receive',id:1,text:'{}'});await f.send({type:'close'});f.controller.close();await microtasks();
  assert.deepEqual(bootstrapSnapshot(f),before,'failed bootstrap must have no export, cleanup or retry authority');
  assert.equal(f.posted.filter(value=>value.type==='error').length,1);assert.equal(f.posted.some(value=>value.type==='ready'),false);
}

test('physical retained profile requires actual kernel agreement before the engine factory and Package preparation',async()=>{
  for(const kernelProfile of ['web','both']){
    const f=fixture({physicalInput:true});f.message.kernelProfile=kernelProfile;
    f.kernel._gui_web_engine_profile_v1=()=>kernelProfile==='web'?1:2;
    const create=f.factories.engine;
    f.factories.engine=options=>{
      assert.deepEqual(f.events,[['kernel-input-describe',0]],'physical facts must precede every engine/Package effect');
      assert.equal(f.kernel.freed.length,1,'read-only facts own exactly one released scratch allocation');return create(options);
    };
    await f.send(f.message);assert.equal(f.controller.state,'ready');f.step();
    const before=f.engine.calls.filter(value=>value.kind===ENGINE.ADVANCE).length;
    const text=JSON.stringify({epoch:'engine-worker-fixture',seq:'10',operation:{type:'poll'}});
    await f.send({type:'receive',id:72,text});
    assert.equal(f.engine.calls.filter(value=>value.kind===ENGINE.ADVANCE).length,before,'receive queues physical owner entry after returning');
    assert.equal(f.posted.at(-1).type,'response');assert.equal(f.posted.at(-1).id,72);f.step();
    assert.equal(f.engine.calls.filter(value=>value.kind===ENGINE.ADVANCE).length,before+1);
    assert.ok(f.kernel.calls.some(value=>value.kind===OP.PEEK_INPUT));await f.send({type:'close'});assert.equal(f.controller.state,'closed');
  }
});
test('physical profiles reject missing, widened or mismatched metadata before retained factories',async()=>{
  const changes=[value=>{delete value.command_catalog_sha256;},value=>{value.extra=1;},value=>{value.capabilities='259';},
    value=>{value.binding='copied-owner-bridge/direct-worker-v1';},value=>{value.surface_capabilities='8289';},
    value=>{value.surface_protocol_version=2;},value=>{value.mouse_input_version=0;},value=>{value.key_mapping_version=2;},
    value=>{value.viewport_width=801;},value=>{value.viewport_height=601;},value=>{value.display_scale=2;},
    value=>{value.command_catalog_sha256='A'.repeat(64);}];
  for(const change of changes){const f=fixture({physicalInput:true});change(f.message.engineProfile);await f.send(f.message);
    assert.equal(f.controller.state,'failed');assert.equal(f.factoryCount,0);assert.deepEqual(f.kernel.calls,[]);assert.deepEqual(f.kernel.ccalls,[]);}
});
test('missing, disabled, malformed or disagreeing physical kernel facts stop before engine construction',async()=>{
  const variants=[kernel=>{delete kernel._gui_web_engine_input_describe_v1;},kernel=>{kernel._gui_web_engine_input_describe_v1=()=>-3;},
    kernel=>{kernel._gui_web_engine_input_describe_v1=()=>0;},kernel=>{kernel._gui_web_engine_input_describe_v1=()=>4096;},
    kernel=>{kernel._gui_web_engine_input_describe_v1=pointer=>{kernel.HEAPU8.set(encoder.encode('{}'),pointer);return 2;};},
    kernel=>{kernel._gui_web_engine_input_describe_v1=pointer=>{const value=physicalProfile();value.command_catalog_sha256='5'.repeat(64);
      const encoded=encoder.encode(JSON.stringify(value));kernel.HEAPU8.set(encoded,pointer);return encoded.length;};}];
  for(const change of variants){const f=fixture({physicalInput:true});change(f.kernel);await f.send(f.message);
    assert.equal(f.controller.state,'failed');assert.equal(f.factoryCount,1);assert.deepEqual(f.kernel.calls,[]);assert.deepEqual(f.engine.calls,[]);
    assert.equal(f.kernel.ccalls.filter(value=>value.name==='gui_web_destroy').length,0);
    for(const value of f.ownWasmURLs)assert.equal(resolveObjectURL(value.url),undefined);}
  const trapped=fixture({physicalInput:true});trapped.kernel._gui_web_engine_input_describe_v1=()=>{throw Error('physical describe trap');};
  await trapped.send(trapped.message);assert.equal(trapped.controller.state,'failed');assert.equal(trapped.factoryCount,1);
  assert.deepEqual(trapped.kernel.freed,[],'a trapped kernel gets no free or destructor exports');assert.deepEqual(trapped.kernel.calls,[]);
});
test('physical engine actual DESCRIBE must match every kernel and retained field before Package preparation',async()=>{
  const actual=physicalProfile();actual.command_catalog_sha256='5'.repeat(64);
  const f=fixture({physicalInput:true,describedProfile:actual});await f.send(f.message);
  assert.equal(f.controller.state,'failed');assert.equal(f.factoryCount,2);assert.deepEqual(f.kernel.calls,[]);
  assert.deepEqual(f.engine.calls.map(value=>value.kind),[ENGINE.DESCRIBE]);
});

test('explicit document profiles inspect actual new kernel facts before engine construction and queue ordinary receive entry',async()=>{
  for(const physical of [false,true])for(const kernelProfile of ['web','both']){
    const f=fixture({documentInput:physical?'physical':'pixel'});f.message.kernelProfile=kernelProfile;
    f.kernel._gui_web_engine_profile_v1=()=>kernelProfile==='web'?1:2;
    f.kernel._gui_web_engine_input_describe_v1=()=>{throw Error('New document profile must not infer legacy physical admission');};
    const create=f.factories.engine;
    f.factories.engine=options=>{
      assert.deepEqual(f.events,[['kernel-document-describe',0]]);assert.equal(f.kernel.freed.length,1);
      assert.equal(f.kernel.calls.length,0);return create(options);
    };
    await f.send(f.message);assert.equal(f.controller.state,'ready');f.step();
    assert.deepEqual(f.documentBootstrap.configure,[{lo:4294967294,hi:4294967295}]);
    assert.deepEqual(f.documentBootstrap.markers,[0,BRIDGE_VERSION]);assert.deepEqual(f.documentBootstrap.freedAtConfigure,[1]);
    assert.equal(f.documentBootstrap.facts.length,1);assert.equal(f.documentBootstrap.facts[0].capacity,4096);
    const order=f.events.map(value=>value[0]==='engine'||value[0]==='kernel'?value.join(':'):value[0]);
    for(const [earlier,later]of [['engine-document-facts','engine-document-configure'],['engine-document-configure','engine:'+ENGINE.DESCRIBE],
      ['engine:'+ENGINE.DESCRIBE,'kernel:'+OP.CONFIGURE],['kernel:'+OP.CONFIGURE,'engine:'+ENGINE.START]])
      assert.ok(order.indexOf(earlier)<order.indexOf(later),earlier+' must precede '+later);
    assert.equal(f.engine.calls.find(value=>value.kind===ENGINE.START).identity.worker,U64_MAX-1n);
    const before=f.engine.calls.filter(value=>value.kind===ENGINE.ADVANCE).length;
    await f.send({type:'receive',id:91,text:JSON.stringify({epoch:'engine-worker-fixture',seq:'11',operation:{type:'poll'}})});
    assert.equal(f.engine.calls.filter(value=>value.kind===ENGINE.ADVANCE).length,before);
    assert.equal(f.posted.at(-1).type,'response');f.step();
    assert.equal(f.engine.calls.filter(value=>value.kind===ENGINE.ADVANCE).length,before+1);
    assert.ok(f.kernel.calls.some(value=>value.kind===OP.PEEK_DOCUMENT_WORK));
    assert.equal(f.kernel.calls.some(value=>value.kind===OP.PEEK_INPUT),physical);
    await f.send({type:'close'});assert.equal(f.controller.state,'closed');
  }
});
test('document profile field, pin, ABI and mask changes fail before any retained factory',async()=>{
  const changes=[p=>{delete p.provider_abi_minor;},p=>{p.extra=true;},p=>{p.capabilities='259';},p=>{p.capabilities='467';},
    p=>{p.capabilities=1795;},p=>{p.provider_abi_minor=0;},p=>{p.provider_abi_minor=2;},p=>{p.host_abi_minor=1;},
    p=>{p.document_profile='foundation-engine-copied259-v1';},p=>{p.binding='copied-owner-bridge/direct-worker-v1';},
    p=>{p.build_sha256='0'.repeat(64);},p=>{p.source_recipe_sha256='0'.repeat(64);},
    ...['contract_sha256','base_header_sha256','extension_header_sha256','document_catalog_sha256','document_schema_sha256','action_ack_schema_sha256']
      .map(key=>p=>{p[key]='5'.repeat(64);})];
  for(const physical of [false,true])for(const change of changes){
    const f=fixture({documentInput:physical?'physical':'pixel'});change(f.message.engineProfile);await f.send(f.message);
    assert.equal(f.controller.state,'failed');assert.equal(f.factoryCount,0);assert.deepEqual(f.kernel.calls,[]);assert.deepEqual(f.kernel.ccalls,[]);
  }
});
test('absent disabled trapped or mismatched new kernel getter never constructs the engine or prepares a Package',async()=>{
  for(const physical of [false,true])for(const change of [
    f=>{delete f.kernel._gui_web_engine_document_describe_v1;},
    f=>{f.kernel._gui_web_engine_document_describe_v1=()=>-3;},
    f=>{f.kernel._gui_web_engine_document_describe_v1=()=>4096;},
    f=>{f.kernel._gui_web_engine_document_describe_v1=pointer=>{f.kernel.HEAPU8.set(encoder.encode('{}'),pointer);return 2;};},
    f=>{f.message.engineProfile.build_sha256='9'.repeat(64);}]){
    const f=fixture({documentInput:physical?'physical':'pixel'});change(f);await f.send(f.message);
    assert.equal(f.controller.state,'failed');assert.equal(f.factoryCount,1);assert.deepEqual(f.kernel.calls,[]);assert.deepEqual(f.engine.calls,[]);
    assert.equal(f.kernel.ccalls.some(value=>value.name==='gui_web_destroy'),false);
  }
  const trapped=fixture({documentInput:'pixel'});trapped.kernel._gui_web_engine_document_describe_v1=()=>{throw Error('document facts trap');};
  await trapped.send(trapped.message);assert.equal(trapped.controller.state,'failed');assert.equal(trapped.factoryCount,1);
  assert.deepEqual(trapped.kernel.freed,[]);assert.deepEqual(trapped.kernel.calls,[]);
});
test('new document engine DESCRIBE must match compiled and retained fields before Package preparation',async()=>{
  for(const physical of [false,true]){
    const actual=documentProfile(physical);actual.build_sha256='9'.repeat(64);
    const f=fixture({documentInput:physical?'physical':'pixel',describedProfile:actual});await f.send(f.message);
    assert.equal(f.controller.state,'failed');assert.equal(f.factoryCount,2);assert.deepEqual(f.kernel.calls,[]);
    assert.deepEqual(f.engine.calls.map(value=>value.kind),[ENGINE.DESCRIBE]);
  }
});
test('document bootstrap preserves full Worker identity and owned4095-byte facts through heap growth',async()=>{
  for(const physical of [false,true]){
    const f=fixture({documentInput:physical?'physical':'pixel'}),raw=encoder.encode(JSON.stringify(documentProfile(physical)));
    const padded=new Uint8Array(4095).fill(32);padded.set(raw);let scratch,released=false;
    f.engine.onMalloc=()=>{if(!f.documentBootstrap.configure.length)f.engine.grow();};
    const facts=f.engine._bib_engine_wasm_document_facts_v1;
    f.engine._bib_engine_wasm_document_facts_v1=(pointer,capacity)=>{
      scratch=pointer;f.engine.grow();facts(pointer,capacity);f.engine.HEAPU8.set(padded,pointer);f.engine.grow();return padded.length;
    };
    f.engine.onFree=pointer=>{if(!released&&pointer===scratch){released=true;f.engine.HEAPU8.fill(0,pointer,pointer+4096);f.engine.grow();}};
    await f.send(f.message);assert.equal(f.controller.state,'ready');assert.equal(released,true);
    assert.deepEqual(f.documentBootstrap.configure,[{lo:4294967294,hi:4294967295}]);
    assert.deepEqual(f.documentBootstrap.markers,[0,BRIDGE_VERSION]);assert.deepEqual(f.documentBootstrap.freedAtConfigure,[1]);
    assert.equal(f.documentBootstrap.facts.length,1);assert.equal(f.engine.calls.filter(value=>value.kind===ENGINE.START).length,1);
    await f.send({type:'close'});assert.equal(f.controller.state,'closed');
  }
});
test('document bootstrap preflights all six required exports before marker or allocation',async()=>{
  for(const [name,replacement]of [['_bib_engine_wasm_document_facts_v1',undefined],['_bib_engine_wasm_document_facts_v1',1],
    ['_bib_engine_wasm_document_configure_v1',undefined],['_bib_engine_wasm_document_configure_v1',{}],['_bib_engine_wasm_dispatch_v1',undefined],
    ['_bib_engine_wasm_bridge_v1',undefined],['_malloc',undefined],['_free',undefined]]){
    const f=fixture({documentInput:'pixel'});if(replacement===undefined)delete f.engine[name];else f.engine[name]=replacement;
    await f.send(f.message);await assertBootstrapStopped(f);assert.deepEqual(f.engine.exports,[]);assert.deepEqual(f.engine.allocations,[]);
  }
});
test('document facts counts UTF8 JSON and exact profile refusals never free or configure',async()=>{
  const valid=documentProfile(),raw=JSON.stringify(valid);
  const malformed=[bytes([255]),encoder.encode(raw+'\0'),encoder.encode('\ufeff'+raw),encoder.encode(raw.slice(0,-1)),
    encoder.encode(raw.replace('{','{"schema_version":1,')),encoder.encode(raw.replace('{','{"\\u0073chema_version":1,')),
    encoder.encode(JSON.stringify({...valid,build_sha256:'9'.repeat(64)})),encoder.encode(JSON.stringify({...valid,extra:true})),
    encoder.encode(JSON.stringify(documentProfile(true)))];
  for(const value of [-1,0,4096,4097,1.5,undefined,'1',...malformed]){
    const f=fixture({documentInput:'pixel'});let cutoff;
    f.engine._bib_engine_wasm_document_facts_v1=(pointer,capacity)=>{
      f.engine.exports.push('document-facts-refusal');assert.equal(capacity,4096);
      cutoff??=bootstrapSnapshot(f);
      if(value instanceof Uint8Array){f.engine.HEAPU8.set(value,pointer);return value.length;}return value;
    };
    await f.send(f.message);assert.ok(cutoff,'facts refusal must be reached');await assertBootstrapStopped(f,cutoff);
    assert.equal(f.engine.freed.length,0);assert.equal(f.documentBootstrap.configure.length,0);
    assert.deepEqual(f.documentBootstrap.markers,[0]);assert.equal(f.engine.allocations.length,1);
  }
});
test('document facts allocation spans and preconfiguration marker must be valid before facts',async()=>{
  for(const pointer of [0,-1,0.5,Number.MAX_SAFE_INTEGER]){
    const f=fixture({documentInput:'pixel'}),allocate=f.engine._malloc;
    f.engine._malloc=length=>{allocate(length);return pointer;};
    await f.send(f.message);await assertBootstrapStopped(f);
    assert.equal(f.documentBootstrap.facts.length,0);assert.equal(f.documentBootstrap.configure.length,0);assert.equal(f.engine.freed.length,0);
  }
  for(const marker of [1,BRIDGE_VERSION]){
    const f=fixture({documentInput:'pixel'});f.engine._bib_engine_wasm_bridge_v1=()=>{f.engine.exports.push('premarker-refusal');return marker;};
    await f.send(f.message);await assertBootstrapStopped(f);assert.equal(f.engine.allocations.length,0);
  }
});
test('document configure refusal and missing configured marker allow no later export or cleanup',async()=>{
  for(const result of [-3,1,undefined,'0',NaN,Promise.resolve(0)]){
    const f=fixture({documentInput:'pixel'}),configure=f.engine._bib_engine_wasm_document_configure_v1;
    let cutoff;f.engine._bib_engine_wasm_document_configure_v1=(...args)=>{configure(...args);cutoff??=bootstrapSnapshot(f);return result;};
    await f.send(f.message);assert.ok(cutoff,'configure refusal must be reached');await assertBootstrapStopped(f,cutoff);
    assert.equal(f.documentBootstrap.configure.length,1);assert.deepEqual(f.documentBootstrap.markers,[0]);
    assert.equal(f.engine.freed.length,1);assert.equal(f.engine.exports.at(-1),'document-configure');
  }
  for(const marker of [0,1]){
    const f=fixture({documentInput:'pixel'}),actual=f.engine._bib_engine_wasm_bridge_v1;let cutoff;
    f.engine._bib_engine_wasm_bridge_v1=()=>{const value=actual();if(value!==0)cutoff??=bootstrapSnapshot(f);return value===0?0:marker;};
    await f.send(f.message);assert.ok(cutoff,'configured marker refusal must be reached');await assertBootstrapStopped(f,cutoff);
    assert.equal(f.documentBootstrap.configure.length,1);assert.equal(f.engine.freed.length,1);
  }
});
test('document bootstrap traps never invoke a later export or compensating free',async()=>{
  for(const stage of ['premarker','malloc','facts','free','configure','postmarker']){
    const f=fixture({documentInput:'pixel'});let cutoff;
    const trap=()=>{cutoff??=bootstrapSnapshot(f);throw Error(stage+' trap');};
    if(stage==='malloc')f.engine.onMalloc=trap;
    else if(stage==='free')f.engine.onFree=trap;
    else{
      const name=stage==='facts'?'_bib_engine_wasm_document_facts_v1':stage==='configure'?'_bib_engine_wasm_document_configure_v1':'_bib_engine_wasm_bridge_v1';
      const actual=f.engine[name];f.engine[name]=(...args)=>{
        const value=actual(...args);if(stage!=='postmarker'||value!==0)trap();return value;
      };
    }
    await f.send(f.message);assert.ok(cutoff,stage+' trap must be reached');await assertBootstrapStopped(f,cutoff);
    assert.equal(f.engine.freed.length,['free','configure','postmarker'].includes(stage)?1:0);
    assert.equal(f.documentBootstrap.configure.length,['configure','postmarker'].includes(stage)?1:0);
  }
});
test('caught Host callbacks from every document metadata phase revoke all later export authority',async()=>{
  for(const stage of ['export-getter','heap-getter','malloc','facts','free','configure']){
    const f=fixture({documentInput:'pixel'}),create=f.factories.engine;let cutoff;
    f.factories.engine=async options=>{
      const module=await create(options),poison=()=>{
        cutoff??=bootstrapSnapshot(f);assert.throws(()=>options.foundationEngineHost(HOST.WAKE,0,0,0,0),/before copied bridge/);
      };
      if(stage==='export-getter'){
        const actual=module._bib_engine_wasm_document_facts_v1;
        Object.defineProperty(module,'_bib_engine_wasm_document_facts_v1',{get(){poison();return actual;}});
      }else if(stage==='heap-getter'){
        const actual=Object.getOwnPropertyDescriptor(module,'HEAPU8').get;
        Object.defineProperty(module,'HEAPU8',{get(){poison();return actual.call(module);}});
      }else if(stage==='malloc')module.onMalloc=poison;
      else if(stage==='free')module.onFree=poison;
      else{
        const name=stage==='facts'?'_bib_engine_wasm_document_facts_v1':'_bib_engine_wasm_document_configure_v1',actual=module[name];
        module[name]=(...args)=>{const result=actual(...args);poison();return result;};
      }
      return module;
    };
    await f.send(f.message);assert.ok(cutoff,stage+' callback must be reached');await assertBootstrapStopped(f,cutoff);
    assert.equal(f.engine.freed.length,['free','configure'].includes(stage)?1:0);
    assert.equal(f.documentBootstrap.configure.length,stage==='configure'?1:0);
  }
});
test('document bootstrap reentrant and repeated init cannot configure again or resume after failure',async()=>{
  for(const stage of ['facts','configure']){
    const f=fixture({documentInput:'pixel'}),name=stage==='facts'?'_bib_engine_wasm_document_facts_v1':'_bib_engine_wasm_document_configure_v1',actual=f.engine[name];
    let reentered,cutoff;f.engine[name]=(...args)=>{const result=actual(...args);cutoff??=bootstrapSnapshot(f);reentered=f.send(f.message);return result;};
    await f.send(f.message);assert.ok(cutoff,stage+' init reentry must be reached');await reentered;await assertBootstrapStopped(f,cutoff);
    assert.equal(f.documentBootstrap.configure.length,stage==='configure'?1:0);assert.equal(f.engine.freed.length,stage==='configure'?1:0);
  }
  for(const stage of ['facts','configure','postmarker','kernel-marker']){
    const f=fixture({documentInput:'pixel'}),module=stage==='kernel-marker'?f.kernel:f.engine;
    const name=stage==='facts'?'_bib_engine_wasm_document_facts_v1':stage==='configure'?'_bib_engine_wasm_document_configure_v1':
      stage==='kernel-marker'?'_gui_web_engine_bridge_v1':'_bib_engine_wasm_bridge_v1',actual=module[name];
    let closed,cutoff;module[name]=(...args)=>{
      const result=actual(...args);if(stage!=='postmarker'||result!==0){cutoff??=bootstrapSnapshot(f);closed=f.send({type:'close'});}return result;
    };
    await f.send(f.message);assert.ok(cutoff,stage+' close reentry must be reached');await closed;await assertBootstrapStopped(f,cutoff);
    assert.equal(f.documentBootstrap.configure.length,['configure','postmarker'].includes(stage)?1:0);
    assert.equal(f.engine.freed.length,['configure','postmarker'].includes(stage)?1:0);
  }
  const f=fixture({documentInput:'pixel'});await f.send(f.message);assert.equal(f.controller.state,'ready');
  const exports=f.engine.exports.length;await f.send(f.message);assert.equal(f.controller.state,'failed');
  assert.equal(f.engine.exports.length,exports);assert.equal(f.documentBootstrap.configure.length,1);f.step();
  assert.equal(f.engine.exports.length,exports);assert.equal(f.posted.filter(value=>value.type==='ready').length,1);
});
test('legacy259 and467 never inspect document facts or configure a document worker',async()=>{
  for(const physicalInput of [false,true]){
    const f=fixture({physicalInput});
    f.engine._bib_engine_wasm_document_facts_v1=()=>{throw Error('legacy document facts entry');};
    f.engine._bib_engine_wasm_document_configure_v1=()=>{throw Error('legacy document configure entry');};
    await f.send(f.message);assert.equal(f.controller.state,'ready');assert.deepEqual(f.documentBootstrap.configure,[]);
    assert.equal(f.engine.exports.filter(value=>value==='engine-marker').length,1);
    assert.equal(f.engine.calls.filter(value=>value.kind===ENGINE.START).length,1);await f.send({type:'close'});
    assert.equal(f.controller.state,'closed');
  }
});

test('invalid engine/kernel profiles and Worker identities fail before retained factories or kernel preparation',async()=>{
  const changes=[value=>{value.engineProfile.pthread=true;},value=>{value.engineProfile.shared_memory=true;},
    value=>{value.engineProfile.pointer_bits=64;},value=>{value.engineProfile.binding='proxy-to-pthread';},
    value=>{value.engineProfile.capabilities='258';},value=>{value.engineProfile.capabilities='467';},value=>{value.engineProfile.capabilities='0259';},
    value=>{value.engineProfile.capabilities='259\n';},value=>{value.engineProfile.build_sha256='x'.repeat(64);},
    value=>{value.workerEpoch='0';},value=>{value.workerEpoch='01';},value=>{value.workerEpoch=String(U64_MAX+1n);},
    value=>{value.workerEpoch='1\n';},value=>{value.prefixSha256='0'.repeat(64)+'\n';},
    value=>{delete value.kernelProfile;},...['binary','minimal','Web','web\n','',null,1,{},['web']].map(kernelProfile=>value=>{value.kernelProfile=kernelProfile;})];
  for(const change of changes){const f=fixture();change(f.message);await f.send(f.message);
    assert.equal(f.controller.state,'failed');assert.equal(f.factoryCount,0);assert.equal(f.kernel.calls.length,0);
    assert.equal(f.kernel.ccalls.length,0);
    assert.equal(f.posted.length,1);assert.equal(f.posted[0].type,'error');assert.equal(f.closed,1);}
});
test('missing malformed or colliding own Wasm lookup names reject before either retained factory',async()=>{
  const malformed=[undefined,null,1,false,{},[],new String('embedder.wasm'),'','../embedder.wasm','dir/embedder.wasm',
    'dir\\embedder.wasm','./embedder.wasm','a..wasm','a%2ewasm','a.wasm?x','a.wasm#x',' a.wasm','a.wasm ',
    'a.wasm\n','a\u0000.wasm','é.wasm','💾.wasm','a'.repeat(129)];
  const changes=[value=>{delete value.kernelWasmLookup;},value=>{delete value.engineWasmLookup;},
    ...[...malformed,'other.wasm','GUI_appended_engine_wasm.wasm'].map(name=>value=>{value.kernelWasmLookup=name;}),
    ...malformed.map(name=>value=>{value.engineWasmLookup=name;}),
    value=>{value.engineAssets[value.engineWasmLookup]=bytes([1,2,3]);}];
  for(const change of changes){
    const f=fixture();change(f.message);await f.send(f.message);
    assert.equal(f.controller.state,'failed');assert.equal(f.factoryCount,0);
    assert.deepEqual(f.loads,[]);assert.deepEqual(f.ownWasmURLs,[]);
    assert.equal(f.kernel.calls.length,0);assert.equal(f.kernel.ccalls.length,0);assert.equal(f.engine.calls.length,0);
    assert.equal(f.posted.length,1);assert.equal(f.posted[0].type,'error');assert.equal(f.closed,1);
  }
});
test('eager own Wasm lookups return exact owned bytes and never infer a basename or reuse data assets',async()=>{
  for(const engineName of [defaultEngineWasmLookup,'engine-v2_1.wasm','e'.repeat(123)+'.wasm']){
    const f=fixture({engineWasmLookup:engineName});await f.send(f.message);
    assert.equal(f.controller.state,'ready');assert.equal(f.ownWasmURLs.length,2);
    assert.deepEqual(f.ownWasmURLs.map(value=>[value.role,value.name]),[['kernel',kernelWasmLookup],['engine',engineName]]);
    assert.notEqual(f.ownWasmURLs[0].url,f.ownWasmURLs[1].url,'separate instances own separate Wasm Blob URLs');
    for(const value of f.ownWasmURLs){
      const expected=value.role==='kernel'?f.message.wasmBinary:f.message.engineWasmBinary;
      assert.deepEqual(new Uint8Array(await value.blob.arrayBuffer()),expected);
      assert.ok(resolveObjectURL(value.url),'own Wasm URL must remain registered before close');
      const options=f.loads.find(item=>item.role===value.role).options;
      assert.equal(options.locateFile(value.name),value.url,'own lookup must stay stable throughout its owner lifetime');
      for(const unknown of ['./'+value.name,'dir/'+value.name,value.name+'?x',value.name+'#x',value.url])
        assert.throws(()=>options.locateFile(unknown),/Unretained/,'only the exact pinned filename is authority');
    }
    const dataURL=f.loads[1].options.locateFile('retained.data');
    assert.ok(f.ownWasmURLs.every(value=>value.url!==dataURL));
    assert.deepEqual(new Uint8Array(await resolveObjectURL(dataURL).arrayBuffer()),bytes([7,8,9]));
    await f.send({type:'close'});assert.equal(f.controller.state,'closed');
    for(const value of f.ownWasmURLs)assert.equal(resolveObjectURL(value.url),undefined,'close must revoke own Wasm Blob URLs');
  }
});
test('a valid but mismatched engine lookup fails at its eager factory before exports or Package preparation',async()=>{
  const f=fixture();f.message.engineWasmLookup='different.wasm';
  f.factories.engine=async options=>{
    f.ownLookup('engine',options,f.message.engineWasmLookup);
    // wasmBinary being present must not make an unpinned lookup succeed.
    options.locateFile(defaultEngineWasmLookup);
    throw Error('mismatched actual factory lookup unexpectedly succeeded');
  };
  await f.send(f.message);assert.equal(f.controller.state,'failed');assert.equal(f.factoryCount,2);
  assert.match(f.posted[0].message,/Unretained/);assert.deepEqual(f.kernel.ccalls,[profileQuery]);
  assert.equal(f.kernel.calls.length,0);assert.equal(f.engine.calls.length,0);
  assert.equal(f.ownWasmURLs.length,2);
  for(const value of f.ownWasmURLs)assert.equal(resolveObjectURL(value.url),undefined,'failed eager lookup must revoke both owned binaries');
});
test('compiled kernel profile rejects missing exports, malformed results, mismatches and traps before the engine factory',async()=>{
  const changes=[
    {name:'missing raw export',apply:f=>{delete f.kernel._gui_web_engine_profile_v1;},queries:0},
    {name:'nonfunction raw export',apply:f=>{f.kernel._gui_web_engine_profile_v1=1;},queries:0},
    {name:'missing ccall',apply:f=>{delete f.kernel.ccall;},queries:0},
    {name:'nonfunction ccall',apply:f=>{f.kernel.ccall={};},queries:0},
    {name:'web descriptor with both kernel',apply:f=>{f.kernel._gui_web_engine_profile_v1=()=>2;},queries:1},
    {name:'both descriptor with web kernel',apply:f=>{f.message.kernelProfile='both';},queries:1},
    {name:'query trap',apply:f=>{f.kernel._gui_web_engine_profile_v1=()=>{throw Error('fixture profile query trap');};},queries:1},
    ...[0,3,-1,NaN,Infinity,'1',1n,true,null,undefined,Promise.resolve(1)].map(result=>({name:'malformed '+String(result),
      apply:f=>{f.kernel._gui_web_engine_profile_v1=()=>result;},queries:1}))];
  for(const change of changes){const f=fixture();change.apply(f);await f.send(f.message);
    assert.equal(f.controller.state,'failed',change.name);assert.equal(f.factoryCount,1,change.name);
    assert.equal(f.kernel.calls.length,0,change.name+' must precede CONFIGURE');assert.equal(f.engine.calls.length,0,change.name);
    assert.deepEqual(f.kernel.ccalls,Array.from({length:change.queries},()=>profileQuery),change.name);
    assert.equal(f.posted.length,1);assert.equal(f.posted[0].type,'error');assert.equal(f.closed,1);
    for(const value of f.ownWasmURLs)assert.equal(resolveObjectURL(value.url),undefined,change.name+' must revoke its own Wasm URL');
  }
});
test('web and both profiles query their matching compiled kernel exactly once before the engine factory and preparation',async()=>{
  for(const [declared,compiled]of [['web',1],['both',2]]){
    const f=fixture();f.message.kernelProfile=declared;f.kernel._gui_web_engine_profile_v1=()=>compiled;
    const createEngine=f.factories.engine;
    f.factories.engine=async options=>{
      assert.deepEqual(f.kernel.ccalls,[profileQuery],'engine factory must follow the read-only compiled profile query');
      assert.equal(f.kernel.calls.length,0,'compiled profile must be checked before CONFIGURE');return createEngine(options);
    };
    await f.send(f.message);assert.equal(f.controller.state,'ready',declared);assert.equal(f.factoryCount,2);
    assert.deepEqual(f.kernel.ccalls.filter(value=>value.name===profileQuery.name),[profileQuery]);
    assert.equal(f.kernel.calls.filter(value=>value.kind===OP.CONFIGURE).length,1);
    assert.equal(f.engine.calls.filter(value=>value.kind===ENGINE.START).length,1);
    await f.send({type:'close'});assert.equal(f.controller.state,'closed');
  }
});
test('the optional raw composition getter preserves legacy startup and queries web5 or both7 before the engine factory',async()=>{
  for(const [declared,result]of [['web',null],['web',5],['both',7]]){
    const f=fixture();f.message.kernelProfile=declared;f.kernel._gui_web_engine_profile_v1=()=>declared==='web'?1:2;
    let queries=0;
    if(result!==null)f.kernel._gui_web_application_composition_v1=function(){
      assert.equal(this,f.kernel,'the raw getter receives its owning module');++queries;return result;
    };
    else assert.equal(Object.hasOwn(f.kernel,'_gui_web_application_composition_v1'),false);
    const createEngine=f.factories.engine;
    f.factories.engine=async options=>{
      assert.equal(queries,result===null?0:1,'the composition query must precede the engine factory');
      assert.deepEqual(f.kernel.ccalls,[profileQuery],'the optional raw getter must not use ccall');
      assert.equal(f.kernel.calls.length,0,'composition admission must precede CONFIGURE');
      assert.equal(f.engine.calls.length,0);return createEngine(options);
    };
    await f.send(f.message);assert.equal(f.controller.state,'ready');assert.equal(f.factoryCount,2);
    assert.equal(queries,result===null?0:1);
    assert.deepEqual(f.kernel.ccalls.filter(value=>value.name===profileQuery.name),[profileQuery]);
    assert.equal(f.kernel.ccalls.some(value=>value.name==='gui_web_application_composition_v1'),false);
    assert.equal(f.kernel.calls.filter(value=>value.kind===OP.CONFIGURE).length,1);
    assert.equal(f.engine.calls.filter(value=>value.kind===ENGINE.START).length,1);
    await f.send({type:'close'});assert.equal(f.controller.state,'closed');
  }
});
test('present malformed composition getters reject before engine construction and Package preparation',async()=>{
  const changes=[
    {name:'present null',value:null,queries:0},
    {name:'present undefined',value:undefined,queries:0},
    {name:'query trap',trap:true,queries:1},
    ...[true,5.5,NaN,7,1].map(value=>({name:'invalid web result '+String(value),value,queries:1,callable:true})),
    {name:'invalid both result 5',value:5,queries:1,callable:true,profile:'both'}];
  for(const change of changes){
    const f=fixture();let queries=0;
    f.message.kernelProfile=change.profile||'web';
    f.kernel._gui_web_engine_profile_v1=()=>change.profile==='both'?2:1;
    f.kernel._gui_web_application_composition_v1=change.trap?function(){++queries;throw Error('fixture composition query trap');}:
      change.callable?function(){++queries;return change.value;}:change.value;
    await f.send(f.message);assert.equal(f.controller.state,'failed',change.name);
    assert.equal(queries,change.queries,change.name);assert.equal(f.factoryCount,1,change.name);
    assert.deepEqual(f.kernel.ccalls,[profileQuery]);assert.equal(f.kernel.calls.length,0);assert.equal(f.engine.calls.length,0);
    assert.equal(f.posted.length,1);assert.equal(f.posted[0].type,'error');assert.equal(f.closed,1);
    assert.match(f.posted[0].message,change.trap?/fixture composition query trap/:/composition/);
    for(const value of f.ownWasmURLs)assert.equal(resolveObjectURL(value.url),undefined,'rejection must revoke its owned Wasm URL');
  }
});
test('missing or incompatible actual markers and compiled profile reject before CONFIGURE',async()=>{
  for(const role of ['kernel','engine'])for(const missing of [false,true]){
    const f=fixture(),marker=role==='kernel'?'_gui_web_engine_bridge_v1':'_bib_engine_wasm_bridge_v1';
    if(missing)delete f[role][marker];else f[role][marker]=()=>1;
    await f.send(f.message);assert.equal(f.controller.state,'failed');
    assert.equal(f.kernel.calls.some(request=>request.kind===OP.CONFIGURE),false);
    assert.equal(f.engine.calls.some(request=>request.kind===ENGINE.START),false);
    assert.deepEqual(f.kernel.ccalls,[profileQuery]);assert.equal(f.posted[0].type,'error');
  }
  const f=fixture({describedProfile:{...profile(),build_sha256:'9'.repeat(64)}});await f.send(f.message);
  assert.equal(f.controller.state,'failed');assert.deepEqual(f.engine.calls.map(value=>value.kind),[ENGINE.DESCRIBE]);
  assert.equal(f.kernel.calls.length,0,'compiled read-only identity rejection must precede preparation');
});
test('retained factory options install callback routing without executing surface application scripts',async()=>{
  const f=fixture();await f.send(f.message);
  assert.equal(f.controller.state,'ready');assert.equal(f.posted[0].type,'ready');
  assert.deepEqual(f.events.slice(0,3),[['engine',ENGINE.DESCRIBE],['kernel',OP.CONFIGURE],['engine',ENGINE.START]]);
  for(const {options}of f.loads){assert.throws(()=>options.locateFile('unretained.data'),/Unretained/);}
  assert.equal(new URL(f.loads[1].options.locateFile('retained.data')).protocol,'blob:');
  const assetURL=f.loads[1].options.locateFile('retained.data');
  const retainedURLs=[...f.factoryURLs,...f.ownWasmURLs.map(value=>value.url),assetURL];
  for(const url of retainedURLs)assert.ok(resolveObjectURL(url),'retained Blob URL must exist during its owner lifetime');
  assert.equal(globalThis.engineFixtureApplicationRan,undefined);
  assert.equal(f.kernel.ccalls.filter(value=>value.name==='gui_web_receive').length,0,'startup must not fabricate a GUI poll');
  f.step();await microtasks();
  for(const operation of [OP.PEEK_RETIREMENT_AUDIT,OP.PEEK_RETIRED_DOCUMENT])
    assert.ok(f.events.some(([role,kind])=>role==='kernel'&&kind===operation),'Worker must query its explicit empty retirement mailbox');
  assert.equal(f.kernel.ccalls.filter(value=>value.name==='gui_web_receive').length,0,'owner task is not a GUI envelope');
  const text=JSON.stringify({epoch:'engine-worker-fixture',seq:'9',operation:{type:'focus',key:{id:'fixture',generation:'1'}}});
  await f.send({type:'receive',id:71,text});
  assert.deepEqual(f.kernel.ccalls.find(value=>value.name==='gui_web_receive').args,[text]);
  assert.equal(f.posted.at(-1).id,71);await f.send({type:'close'});
  assert.equal(f.controller.state,'closed');assert.deepEqual(f.posted.at(-1),{type:'closed'});
  assert.equal(f.kernel.ccalls.filter(value=>value.name==='gui_web_destroy').length,1);
  for(const url of retainedURLs)assert.equal(resolveObjectURL(url),undefined,'closed Worker must revoke every observed retained Blob URL');
  assert.equal(globalThis.engineFixtureApplicationRan,undefined);
});
test('production Worker forwards onDirty and exposes document replay only through its live bridge owner',async()=>{
  assert.throws(()=>installAppendedEngineWasmWorker({},undefined,undefined,null),/Invalid engine Worker document observer/);
  const dirty=[];
  const f=fixture({documentInput:'pixel',onDirty:()=>dirty.push('dirty')});
  await f.send(f.message);
  assert.equal(f.controller.state,'ready');
  const before=dirty.length;
  f.step();await microtasks();
  assert.ok(dirty.length>before,'the installed bridge pump must reach the fourth onDirty callback');
  await assert.rejects(f.controller.replayDocumentCompletion(null),/Invalid document replay selector/,
    'a ready Worker delegates selector validation to the real bridge');
  await f.send({type:'close'});assert.equal(f.controller.state,'closed');

  const starting=fixture({asyncStartup:true}),initializing=starting.send(starting.message);
  await microtasks();assert.equal(starting.controller.state,'starting');
  await assert.rejects(starting.controller.replayDocumentCompletion(null),/live ready Worker owner/);
  await starting.send({type:'close'});await initializing;
  assert.equal(starting.controller.state,'closed');
  await assert.rejects(starting.controller.replayDocumentCompletion(null),/live ready Worker owner/);

  const closing=fixture({documentInput:'pixel',holdFirstClose:true});
  await closing.send(closing.message);assert.equal(closing.controller.state,'ready');
  await closing.send({type:'close'});
  await assert.rejects(closing.controller.replayDocumentCompletion(null),/live ready Worker owner/,
    'the handle must reject as soon as shutdown begins, while the owner drains close');
  for(let count=0;closing.controller.state!=='closed';++count){
    assert.ok(count<10,'pending Worker close must finish through its scheduled owner task');
    await microtasks();
    if(closing.controller.state!=='closed')closing.step();
  }
  await assert.rejects(closing.controller.replayDocumentCompletion(null),/live ready Worker owner/);

  const failed=fixture();await failed.send({type:'unexpected'});
  assert.equal(failed.controller.state,'failed');
  await assert.rejects(failed.controller.replayDocumentCompletion(null),/live ready Worker owner/);
});
test('engine factory cannot call the owner before the copied bridge is installed',async()=>{
  const f=fixture();f.factories.engine=async options=>{f.ownLookup('engine',options);options.foundationEngineHost(HOST.WAKE,0,0,0,0);return f.engine;};
  await f.send(f.message);assert.equal(f.controller.state,'failed');assert.match(f.posted[0].message,/before copied bridge/);
  assert.equal(f.kernel.calls.length,0);assert.equal(f.engine.calls.length,0);
  for(const value of f.ownWasmURLs)assert.equal(resolveObjectURL(value.url),undefined,'failed premature callback must revoke own Wasm URLs');
});
test('a factory cannot catch a premature Host callback and continue into inspection or Package effects',async()=>{
  for(const documentInput of [null,'pixel','physical'])for(const role of ['kernel','engine']){
    const f=fixture({documentInput});
    f.factories[role]=async options=>{
      assert.throws(()=>options.foundationEngineHost(HOST.WAKE,0,0,0,0),/before copied bridge/);
      return f[role];
    };
    await f.send(f.message);assert.equal(f.controller.state,'failed');assert.equal(f.closed,1);
    assert.equal(f.factoryCount,role==='kernel'?1:2);assert.deepEqual(f.kernel.calls,[]);assert.deepEqual(f.engine.calls,[]);
    assert.equal(f.posted.length,1);assert.equal(f.posted[0].type,'error');
    assert.equal(f.kernel.ccalls.some(value=>value.name==='gui_web_destroy'||value.name==='gui_web_create'),false);
  }
});
test('caught forbidden callbacks from compiled queries and bridge markers stop all later export and Package effects',async()=>{
  for(const documentInput of [null,'pixel','physical'])for(const stage of ['marker','facts','kernel-bridge','engine-bridge']){
    const role=stage==='engine-bridge'?'engine':'kernel',f=fixture({documentInput,physicalInput:documentInput===null}),create=f.factories[role];
    let engineMarkers=0;const actualMarker=f.engine._bib_engine_wasm_bridge_v1;
    f.engine._bib_engine_wasm_bridge_v1=()=>{++engineMarkers;return actualMarker();};
    f.factories[role]=async options=>{
      const module=await create(options),name=stage==='marker'?'_gui_web_engine_profile_v1':stage==='kernel-bridge'?'_gui_web_engine_bridge_v1':
        stage==='engine-bridge'?'_bib_engine_wasm_bridge_v1':documentInput?'_gui_web_engine_document_describe_v1':'_gui_web_engine_input_describe_v1',original=module[name];
      module[name]=(...args)=>{assert.throws(()=>options.foundationEngineHost(HOST.WAKE,0,0,0,0),/before copied bridge/);return original(...args);};
      return module;
    };
    await f.send(f.message);assert.equal(f.controller.state,'failed');assert.equal(f.factoryCount,stage.endsWith('bridge')?2:1);assert.equal(f.closed,1);
    assert.deepEqual(f.kernel.calls,[]);assert.deepEqual(f.engine.calls,[]);
    assert.equal(engineMarkers,stage==='engine-bridge'?1:0,'a failed kernel marker must not call the engine marker');
    if(!stage.endsWith('bridge'))assert.deepEqual(f.kernel.freed,[]);
    assert.equal(f.posted.length,1);assert.equal(f.posted[0].type,'error');
    assert.equal(f.kernel.ccalls.some(value=>value.name==='gui_web_create'||value.name==='gui_web_destroy'),false);
  }
});
test('a failed Worker gives queued owner tasks no later endpoint export authority',async()=>{
  const f=fixture({documentInput:'pixel'});await f.send(f.message);assert.equal(f.controller.state,'ready');
  assert.ok(f.tasks.size>0);await f.send({type:'receive',id:0,text:'{}'});assert.equal(f.controller.state,'failed');
  let exports=0;
  for(const module of [f.kernel,f.engine])for(const name of Object.keys(module))if(name.startsWith('_')&&typeof module[name]==='function'){
    const original=module[name];module[name]=(...args)=>{++exports;return original(...args);};
  }
  const calls=f.kernel.calls.length+f.engine.calls.length;f.step();
  assert.equal(exports,0);assert.equal(f.kernel.calls.length+f.engine.calls.length,calls);assert.equal(f.closed,1);
  assert.equal(f.posted.filter(value=>value.type==='error').length,1);
});
test('close during either deferred factory destroys the late kernel without preparation or ready',async()=>{
  for(const role of ['kernel','engine']){
    const f=fixture();let resolveFactory;
    f.factories[role]=options=>{f.ownLookup(role,options);return new Promise(resolve=>{resolveFactory=resolve;});};
    const initializing=f.send(f.message);await microtasks();assert.equal(typeof resolveFactory,'function');
    await f.send({type:'close'});assert.equal(f.closed,0);
    resolveFactory(f[role]);await initializing;
    assert.equal(f.controller.state,'closed');assert.deepEqual(f.posted,[{type:'closed'}]);assert.equal(f.closed,1);
    assert.equal(f.kernel.calls.length,0);assert.equal(f.engine.calls.length,0);
    assert.deepEqual(f.kernel.ccalls.map(value=>value.name),role==='kernel'?['gui_web_destroy']:[profileQuery.name,'gui_web_destroy']);
    for(const value of f.ownWasmURLs)assert.equal(resolveObjectURL(value.url),undefined,'late factory close must revoke its owned binary URL');
  }
});
test('failure while a factory is pending forbids late preparation, exports and a replacement ready',async()=>{
  for(const role of ['kernel','engine']){
    const f=fixture();let resolveFactory;
    f.factories[role]=options=>{f.ownLookup(role,options);return new Promise(resolve=>{resolveFactory=resolve;});};
    const initializing=f.send(f.message);await microtasks();
    await f.send({type:'receive',id:1,text:'{}'});assert.equal(f.controller.state,'failed');
    resolveFactory(f[role]);await initializing;
    assert.equal(f.controller.state,'failed');assert.equal(f.closed,1);
    assert.equal(f.posted.length,1);assert.equal(f.posted[0].type,'error');
    assert.equal(f.kernel.calls.length,0);assert.equal(f.engine.calls.length,0);
    assert.deepEqual(f.kernel.ccalls,role==='kernel'?[]:[profileQuery]);
    assert.equal(f.factoryCount,role==='kernel'?1:2);
    for(const value of f.ownWasmURLs)assert.equal(resolveObjectURL(value.url),undefined,'failed late factory must not resurrect an owned binary URL');
  }
});
test('close before asynchronous document readiness cancels startup and never reports ready',async()=>{
  const f=fixture({asyncStartup:true});const initializing=f.send(f.message);await microtasks();
  assert.equal(f.controller.state,'starting');assert.equal(f.posted.length,0);
  await f.send({type:'close'});await microtasks();
  assert.equal(f.controller.state,'closed','close must not wait for an absent first document or its deadline');
  await initializing;assert.deepEqual(f.posted,[{type:'closed'}]);
  assert.equal(f.kernel.ccalls.filter(value=>value.name==='gui_web_create').length,0);
  assert.equal(f.kernel.ccalls.filter(value=>value.name==='gui_web_destroy').length,1);
  const callCount=f.engine.calls.length;let remaining=0;
  while([...f.tasks.values()].some(item=>item.delay===0||item.delay===1)){
    assert.ok(++remaining<=10,'closed startup tasks must drain without rescheduling');f.step();
  }
  assert.equal(f.engine.calls.length,callCount,'late startup task cannot reenter a retired engine');
});

// Only irrelevant physical DOM/Worker imports are replaced. The production
// suffix/base64/bridge functions themselves are imported without body changes.
// A source-archive checkout need not contain a generated renderer child bundle.
const dataURL=source=>'data:text/javascript;base64,'+Buffer.from(source).toString('base64');
async function verifier({frontendSource,transportSource,channelSource}={}){
  const frontend=dataURL(frontendSource??'export function createEmbeddedFrontend(){throw Error("No DOM boundary in suffix tests");}');
  const transport=dataURL(transportSource??'export function createWasmTransport(){throw Error("No Worker boundary in suffix tests");}');
  const replace=(source,edge,target)=>{assert.equal(source.split(edge).length,2,'reviewed bootstrap import edge changed');return source.replace(edge,target);};
  const binaryURL=new URL('./appended_browser_bootstrap.mjs',bootstrapURL);
  let binary=await readFile(binaryURL,'utf8');
  binary=replace(binary,"'./browser_embedding.mjs'",JSON.stringify(frontend));
  binary=replace(binary,"'./wasm_transport.mjs'",JSON.stringify(transport));
  let rich=await readFile(bootstrapURL,'utf8');
  rich=replace(rich,"'./browser_embedding.mjs'",JSON.stringify(frontend));
  rich=replace(rich,"'./wasm_transport.mjs'",JSON.stringify(transport));
  rich=replace(rich,"'./renderer_channel.mjs'",JSON.stringify(channelSource?dataURL(channelSource):new URL('./renderer_channel.mjs',bootstrapURL).href));
  rich=replace(rich,"'./browser_surface_protocol.mjs'",JSON.stringify(new URL('./browser_surface_protocol.mjs',bootstrapURL).href));
  // The generated renderer namespace is data, unused by verifyEngineSuffix.
  // Do not manufacture a working child renderer or execute any surface code.
  rich=replace(rich,"'./renderer_surface_child_bundle.mjs'",JSON.stringify(dataURL('export const UNUSED_SUFFIX_TEST_BUNDLE=true;')));
  rich=replace(rich,"'./appended_browser_bootstrap.mjs'",JSON.stringify(dataURL(binary)));
  rich=replace(rich,"'./engine_kernel_bridge.mjs'",JSON.stringify(bridgeURL.href));
  return await import(dataURL(rich));
}
const {verifyEngineSuffix,startAppendedEngineBrowser}=await verifier();
test('bootstrap selects the physical browser descriptor explicitly and never mixes its twenty-field profile with copied259',async()=>{
  const descriptor=()=>({schema_version:1,kind:'foundation-copied-engine-physical-browser',kernel_profile:'web',
    kernel_wasm_lookup:kernelWasmLookup,engine_wasm_lookup:defaultEngineWasmLookup,kernel_factory:{},kernel_wasm:{},
    engine_factory:{},engine_wasm:{},engine_profile:physicalProfile(),engine_assets:{},notices:{}});
  const host=()=>{const status={textContent:''},listeners=new Map();return {status,listeners,
    document:{querySelector:name=>name==='#status'?status:name==='#application'?{}:null,querySelectorAll:()=>[]},
    addEventListener:(name,handler)=>listeners.set(name,handler),removeEventListener:name=>listeners.delete(name)};};
  const physicalRendererBundle={CHILD_SCRIPT:'inert reviewed physical data',CHILD_SCRIPT_SHA256:'retained',CHILD_CSP:'retained',
    CHILD_SANDBOX:'allow-scripts',CHILD_PROTOCOL:'retained',CHILD_STYLE:'retained'};
  const accepted=host();await startAppendedEngineBrowser({prefix:vector.prefix,kernel:descriptor(),workerSource:'inert',physicalRendererBundle,host:accepted});
  assert.equal(accepted.status.textContent,'No appended application payload is attached.');assert.equal(accepted.listeners.size,0);
  const replaced={...physicalRendererBundle,extra:'unexpected'};delete replaced.CHILD_SCRIPT;
  const inherited=Object.assign(Object.create(physicalRendererBundle),{one:'x',two:'x',three:'x',four:'x',five:'x',six:'x'});
  let getterCalls=0;const getter={...physicalRendererBundle};Object.defineProperty(getter,'CHILD_SCRIPT',{get(){++getterCalls;return 'not copied';},enumerable:true});
  const symbol={...physicalRendererBundle,[Symbol('unexpected')]:'not data'};
  for(const bundle of [null,{}, {...physicalRendererBundle,extra:'unexpected'}, {...physicalRendererBundle,CHILD_SCRIPT:1},replaced,inherited,getter,symbol]){
    const rejected=host(),document=rejected.document;let domReads=0;Object.defineProperty(rejected,'document',{get(){++domReads;return document;}});
    await assert.rejects(startAppendedEngineBrowser({prefix:vector.prefix,kernel:descriptor(),workerSource:'inert',physicalRendererBundle:bundle,host:rejected}),/physical renderer bundle/);
    assert.equal(rejected.listeners.size,0);assert.equal(domReads,0,'invalid physical renderer data must fail before DOM access');
  }
  assert.equal(getterCalls,0,'physical renderer accessors must never execute');
  const mixed=[value=>{value.kind='foundation-copied-engine-browser';},value=>{value.engine_profile=profile();},
    value=>{value.kind='foundation-copied-engine-physical-browser-v2';},value=>{value.engine_profile.surface_capabilities='8289';}];
  for(const change of mixed){const kernel=descriptor();change(kernel);const rejected=host();
    await assert.rejects(startAppendedEngineBrowser({prefix:vector.prefix,kernel,workerSource:'inert',physicalRendererBundle,host:rejected}),/Unsupported/);
    assert.equal(rejected.listeners.size,0);}
});
test('document browser kind is explicit and cannot upgrade either legacy descriptor or profile',async()=>{
  const renderer={CHILD_SCRIPT:'inert reviewed physical data',CHILD_SCRIPT_SHA256:'retained',CHILD_CSP:'retained',
    CHILD_SANDBOX:'allow-scripts',CHILD_PROTOCOL:'retained',CHILD_STYLE:'retained'};
  const host=()=>{const status={textContent:''},listeners=new Map();return {status,listeners,
    document:{querySelector:name=>name==='#status'?status:name==='#application'?{}:null,querySelectorAll:()=>[]},
    addEventListener:(name,handler)=>listeners.set(name,handler),removeEventListener:name=>listeners.delete(name)};};
  const descriptor=physical=>({schema_version:1,kind:'foundation-copied-engine-document-browser',kernel_profile:'web',
    kernel_wasm_lookup:kernelWasmLookup,engine_wasm_lookup:defaultEngineWasmLookup,kernel_factory:{},kernel_wasm:{},
    engine_factory:{},engine_wasm:{},engine_profile:documentProfile(physical),engine_assets:{},notices:{}});
  for(const physical of [false,true]){
    const accepted=host();await startAppendedEngineBrowser({prefix:vector.prefix,kernel:descriptor(physical),workerSource:'inert',physicalRendererBundle:renderer,host:accepted});
    assert.equal(accepted.status.textContent,'No appended application payload is attached.');assert.equal(accepted.listeners.size,0);
    for(const change of [k=>{k.kind='foundation-copied-engine-browser';},k=>{k.kind='foundation-copied-engine-physical-browser';},
      k=>{k.engine_profile=profile();},k=>{k.engine_profile=physicalProfile();}]){
      const rejected=host(),kernel=descriptor(physical);change(kernel);
      await assert.rejects(startAppendedEngineBrowser({prefix:vector.prefix,kernel,workerSource:'inert',physicalRendererBundle:renderer,host:rejected}),/Unsupported/);
      assert.equal(rejected.listeners.size,0);
    }
  }
});
test('physical trusted renderer injection selects mouse-v1 host validation while legacy keeps its default validator',async()=>{
  const {startAppendedEngineBrowser:start}=await verifier({
    frontendSource:'export function createEmbeddedFrontend(options){globalThis.__engineBootstrapTestOptions=options;return {ready:Promise.resolve(),close(){}};}',
    transportSource:'export function createWasmTransport(){return {ready:Promise.resolve({snapshot:{title:"Engine fixture"}}),exchange(){},close(){return Promise.resolve();}};}',
    channelSource:'export function createHostChannel(options){return options;}'
  });
  const asset=value=>({data:Buffer.from(value).toString('base64'),sha256:sha(value)}),source=asset(encoder.encode('inert retained factory')),
    wasm=asset(bytes([0,97,115,109,1,0,0,0])),physicalRendererBundle={CHILD_SCRIPT:'inert physical renderer data',CHILD_SCRIPT_SHA256:'retained',
      CHILD_CSP:'retained',CHILD_SANDBOX:'allow-scripts',CHILD_PROTOCOL:'retained',CHILD_STYLE:'retained'};
  try{for(const {physical,document} of [{physical:true,document:false},{physical:false,document:false},{physical:true,document:true},{physical:false,document:true}]){
    const suppliedRenderer={...physicalRendererBundle};let touchedDOM=false;
    const kernel={schema_version:1,kind:document?'foundation-copied-engine-document-browser':physical?'foundation-copied-engine-physical-browser':'foundation-copied-engine-browser',kernel_profile:'web',
      kernel_wasm_lookup:kernelWasmLookup,engine_wasm_lookup:defaultEngineWasmLookup,kernel_factory:source,kernel_wasm:wasm,
      engine_factory:source,engine_wasm:wasm,engine_profile:document?documentProfile(physical):physical?physicalProfile():profile(),engine_assets:{},notices:{}};
    const status={textContent:''},listeners=new Map(),node=()=>({append(){}}),host={
      document:{querySelector:name=>{if(!touchedDOM){touchedDOM=true;suppliedRenderer.CHILD_SCRIPT='changed after capture';}
        return name==='#status'?status:name==='#application'?{}:null;},
        querySelectorAll:()=>[{getAttribute:()=> 'application/octet-stream',textContent:vector.encoded}],createElement:node,body:node()},
      addEventListener:(name,handler)=>listeners.set(name,handler),removeEventListener:name=>listeners.delete(name),URL,Blob,crypto:webcrypto};
    const result=await start({prefix:vector.prefix,kernel,workerSource:'inert retained Worker',physicalRendererBundle:suppliedRenderer,host});
    const options=globalThis.__engineBootstrapTestOptions,protocol=options.channelFactory({}).surfaceProtocol;
    const connect={type:'surfaceConnect',version:1,supported:'8225',mouseInputVersion:1};
    if(physical){assert.notEqual(options.rendererBundle,suppliedRenderer);assert.deepEqual(options.rendererBundle,physicalRendererBundle);
      assert.equal(Object.isFrozen(options.rendererBundle),true);assert.equal(Object.getPrototypeOf(options.rendererBundle),Object.prototype);
      assert.equal(protocol.validateSurfaceOperation(connect,null,null),connect);}
    else{assert.notEqual(options.rendererBundle,suppliedRenderer);assert.throws(()=>protocol.validateSurfaceOperation(connect,null,null));}
    result.close();assert.equal(listeners.size,0);
  }}finally{delete globalThis.__engineBootstrapTestOptions;}
});
test('bootstrap requires the pinned own Wasm names and refuses own-name data collisions before a Worker exists',async()=>{
  const asset=value=>({data:Buffer.from(value).toString('base64'),sha256:sha(value)});
  const descriptor=()=>({schema_version:1,kind:'foundation-copied-engine-browser',kernel_profile:'web',
    kernel_wasm_lookup:kernelWasmLookup,engine_wasm_lookup:defaultEngineWasmLookup,
    kernel_factory:asset(encoder.encode('inert retained kernel factory')),kernel_wasm:asset(bytes([0,97,115,109,1,0,0,0])),
    engine_factory:asset(encoder.encode('inert retained engine factory')),engine_wasm:asset(bytes([0,97,115,109,1,0,0,0])),
    engine_profile:profile(),engine_assets:{},notices:{}});
  const changes=[kernel=>{delete kernel.kernel_wasm_lookup;},kernel=>{delete kernel.engine_wasm_lookup;},
    kernel=>{kernel.kernel_wasm_lookup='other.wasm';},kernel=>{kernel.kernel_wasm_lookup='gui_appended_engine_wasm.wasm\n';},
    ...[null,1,'','../embedder.wasm','dir/embedder.wasm','a..wasm','a.wasm\n','a'.repeat(129)].map(name=>kernel=>{kernel.engine_wasm_lookup=name;}),
    kernel=>{kernel.engine_assets[kernel.engine_wasm_lookup]=asset(bytes([1,2,3]));}];
  for(const change of changes){
    const kernel=descriptor();change(kernel);
    const status={textContent:''},mount={},listeners=new Map();let workers=0,createdURLs=0;
    const host={document:{querySelector:name=>name==='#status'?status:name==='#application'?mount:null,
      querySelectorAll:()=>[{getAttribute:()=> 'application/octet-stream',textContent:vector.encoded}]},
      addEventListener:(name,handler)=>listeners.set(name,handler),removeEventListener:name=>listeners.delete(name),
      Worker:class{constructor(){++workers;throw Error('Unexpected physical Worker');}},
      URL:{createObjectURL(){++createdURLs;throw Error('Unexpected Worker URL');},revokeObjectURL(){throw Error('Unexpected Worker URL release');}}};
    await assert.rejects(startAppendedEngineBrowser({prefix:vector.prefix,kernel,workerSource:'inert Worker source',host}),
      /Unsupported retained rich browser descriptor|collides with its own Wasm lookup/);
    assert.equal(workers,0);assert.equal(createdURLs,0);assert.equal(listeners.size,0);
    assert.match(status.textContent,/descriptor|collides/);assert.equal(globalThis.engineFixtureApplicationRan,undefined);
  }
});
test('rich suffix verifier preserves the logical web package and canonical retained boundary without execution',async()=>{
  // These independent golden identities were cross-checked with
  // appended_container.build_package/validate_rich_startup/trailer_bytes.
  assert.equal(vector.logical.length,898);
  assert.equal(sha(vector.logical),'1ed1604ba024ccc7203b378c7d9cf5817f5f91e38186851e1f9dd6d6d336c3d4');
  assert.equal(sha(vector.suffix),'9a97367565f6ff0c628d474342ad8da695e89d36ffc93ce4e60f09d94f4fc55b');
  const prepared=await verifyEngineSuffix(vector.encoded,vector.prefix);
  assert.equal(Object.isFrozen(prepared),true);assert.equal(prepared.prefixLength,vector.prefix.length);
  assert.equal(prepared.prefixSha256,sha(vector.prefix));assert.deepEqual(prepared.suffix,vector.suffix);
  assert.deepEqual(vector.index.requires.capabilities,['foundation.startup.v1']);
  assert.equal(globalThis.engineFixtureApplicationRan,undefined);
});
test('no attached payload is explicit absence and does not read or execute application data',async()=>{
  assert.equal(await verifyEngineSuffix(null,null),null);assert.equal(globalThis.engineFixtureApplicationRan,undefined);
  await assert.rejects(verifyEngineSuffix(vector.encoded,new Uint8Array()),/prefix/);
  await assert.rejects(verifyEngineSuffix('',vector.prefix),/Truncated/);
});
test('prefix, content and index digests plus every trailer boundary reject corruption',async()=>{
  const wrongPrefix=vector.prefix.slice();wrongPrefix[0]^=1;
  await assert.rejects(verifyEngineSuffix(vector.encoded,wrongPrefix),/digest/);
  for(const position of [0,vector.logical.length-1,vector.suffix.length-192+56,vector.suffix.length-192+88,vector.suffix.length-192+120]){
    const suffix=vector.suffix.slice();suffix[position]^=1;
    await assert.rejects(verifyEngineSuffix(Buffer.from(suffix).toString('base64'),vector.prefix),/digest/);
  }
  for(const position of [0,8,12,16,24,32,40,48,152,191]){
    const suffix=vector.suffix.slice();suffix[suffix.length-192+position]^=1;
    await assert.rejects(verifyEngineSuffix(Buffer.from(suffix).toString('base64'),vector.prefix),/trailer|boundary/);
  }
  const oversized=vector.suffix.slice();new DataView(oversized.buffer).setBigUint64(oversized.length-192+16,1n<<63n,true);
  await assert.rejects(verifyEngineSuffix(Buffer.from(oversized).toString('base64'),vector.prefix),/Oversized/);
  await assert.rejects(verifyEngineSuffix(vector.encoded+'\n',vector.prefix),/base64/);
  await assert.rejects(verifyEngineSuffix(vector.encoded.slice(0,-4),vector.prefix));
});

// New editor profile fixtures remain separate from every frozen legacy profile.
const editorContractBytes=await readFile(new URL('../../abi/appended/editor-v1/contract.json',import.meta.url)),
  editorCatalogBytes=await readFile(new URL('../../abi/appended/editor-v1/catalog.json',import.meta.url)),
  editorSchemaBytes=await readFile(new URL('../../abi/appended/editor-v1/binary-schema.json',import.meta.url));
const editorProfile=()=>({...profile(),kind:'foundation-copied-engine-editor-v1',binding:'copied-owner-bridge/direct-worker-editor-v1',capabilities:'2035',
  contract_sha256:sha(editorContractBytes),provider_abi_major:1,provider_abi_minor:1,host_abi_major:1,host_abi_minor:0,
  editor_profile:'foundation-engine-copied2035-ndv2-editor-v1',base_header_sha256:'a8e89da85d34b29a4d1bc454495791fa604b81e3477e48ce8ca902e4333a9c0d',
  document_header_sha256:'7b047bae4d0072ef156ea94ba637566d563fea3a95d43c4c6314afc919b1d626',
  document_contract_sha256:'aba7800e6aab1898f3614f0b1ac53e59b9f622bf1e9d3a413f50d672a3662298',
  document_catalog_sha256:'6e555d4c3bb71fbc965e1ca49671fab64d744913e18f45b9ba273505e0c6bcf5',
  physical_catalog_sha256:'d244e6a17561b49b937ad25058f2d662f4f86063633b716bdb87d0250796a47b',
  editor_header_sha256:editorHeaderSha,editor_catalog_sha256:sha(editorCatalogBytes),editor_schema_sha256:sha(editorSchemaBytes),
  document_schema_sha256:'f11fd061350f8d663dbcdec7cf0a063e4fb0ff3564d285076690f58e8a84143d',
  action_ack_schema_sha256:'1eb6c2d4f56acebc1423d9e2b5bf9a1717a99963a5c3f11f4b9d7b0fe33b50f5',viewport_width:800,viewport_height:600,
  surface_protocol_version:2,surface_capabilities:'8255',mouse_input_version:1,key_mapping_version:1,editor_protocol_version:1,display_scale:1,
  editor_query_max_bytes:236,editor_reply_capacity:1048576,editor_command_max_bytes:1048576});
const editorHeaderSha=sha(await readFile(new URL('../../abi/appended/engine_editor_protocol.h',import.meta.url)));
test('explicit editor2035 validates new kernel facts before engine construction and configures the exact Worker before DESCRIBE',async()=>{
  for(const kernelProfile of ['web','both']){const f=fixture({editorInput:true});f.message.kernelProfile=kernelProfile;f.kernel._gui_web_engine_profile_v1=()=>kernelProfile==='web'?1:2;
    f.kernel._gui_web_engine_document_describe_v1=()=>{throw Error('Editor must not select document facts');};
    f.kernel._gui_web_engine_input_describe_v1=()=>{throw Error('Editor must not select legacy physical facts');};
    const create=f.factories.engine;f.factories.engine=options=>{assert.deepEqual(f.events,[['kernel-editor-describe',0]]);assert.equal(f.kernel.freed.length,1);assert.equal(f.kernel.calls.length,0);return create(options);};
    await f.send(f.message);assert.equal(f.controller.state,'ready');assert.deepEqual(f.documentBootstrap.configure,[{lo:4294967294,hi:4294967295}]);
    assert.deepEqual(f.documentBootstrap.markers,[0,BRIDGE_VERSION]);assert.equal(f.documentBootstrap.facts.length,1);
    const describe=f.engine.calls.findIndex(value=>value.kind===ENGINE.DESCRIBE),start=f.engine.calls.findIndex(value=>value.kind===ENGINE.START);assert.equal(describe,0);assert.ok(start>describe);
    f.step();assert.ok(f.kernel.calls.some(value=>value.kind===OP.PEEK_EDITOR_WORK));assert.ok(f.kernel.calls.some(value=>value.kind===OP.PEEK_DOCUMENT_WORK));assert.ok(f.kernel.calls.some(value=>value.kind===OP.PEEK_INPUT));
    const before=f.engine.calls.filter(value=>value.kind===ENGINE.ADVANCE).length;await f.send({type:'receive',id:912,text:JSON.stringify({epoch:'engine-worker-fixture',seq:'19',operation:{type:'poll'}})});
    assert.equal(f.engine.calls.filter(value=>value.kind===ENGINE.ADVANCE).length,before);f.step();assert.equal(f.engine.calls.filter(value=>value.kind===ENGINE.ADVANCE).length,before+1);
    await f.send({type:'close'});assert.equal(f.controller.state,'closed');
  }
});
test('editor profile cannot silently upgrade259 physical467 document1795 or document2003',async()=>{
  const changes=[p=>{p.kind='foundation-copied-engine-document-v2';},p=>{p.binding='copied-owner-bridge/direct-worker-document-v2';},
    p=>{p.editor_profile='foundation-engine-copied2003-ndv2-v1';},p=>{p.capabilities='2003';},p=>{p.surface_capabilities='8225';},
    p=>{p.surface_protocol_version=1;},p=>{p.editor_protocol_version=0;},p=>{p.editor_reply_capacity=1048577;},p=>{p.editor_query_max_bytes=237;},
    p=>{p.extra=1;},p=>{delete p.editor_schema_sha256;},p=>{p.display_scale=true;},p=>{p.build_sha256='0'.repeat(64);}];
  for(const change of changes){const f=fixture({editorInput:true});change(f.message.engineProfile);await f.send(f.message);assert.equal(f.controller.state,'failed');assert.equal(f.factoryCount,0);assert.deepEqual(f.kernel.calls,[]);assert.deepEqual(f.engine.calls,[]);}
});
test('editor missing or disagreeing compiled kernel facts fail before engine factory Package prepare or cleanup',async()=>{
  for(const change of [f=>{delete f.kernel._gui_web_engine_editor_describe_v1;},f=>{f.kernel._gui_web_engine_editor_describe_v1=()=>-3;},
    f=>{f.kernel._gui_web_engine_editor_describe_v1=()=>4096;},f=>{f.message.engineProfile.build_sha256='9'.repeat(64);},
    f=>{f.kernel._gui_web_engine_editor_describe_v1=()=>{throw Error('editor facts trap');};}]){
    const f=fixture({editorInput:true});change(f);await f.send(f.message);assert.equal(f.controller.state,'failed');assert.equal(f.factoryCount,1);
    assert.equal(f.kernel.freed.length,0);assert.deepEqual(f.kernel.calls,[]);assert.deepEqual(f.engine.calls,[]);assert.equal(f.kernel.ccalls.some(value=>value.name==='gui_web_destroy'),false);
  }
});
test('every editor facts boundary rejects duplicate decoded keys nonfinite numbers invalid UTF8 BOM NUL and lone surrogates',async()=>{
  const raw=JSON.stringify(editorProfile()),mutations=[raw.replace('"kind":','"k\\u0069nd":"duplicate","kind":'),
    raw.replace('"schema_version":1','"schema_version":1e999'),raw.replace('"browser-wasm32"','"\\ud800"'),raw.replace('"browser-wasm32"','"\\udc00"'),
    raw.replace('"browser-wasm32"','"\\u0000"'),'\ufeff'+raw,raw+'\0',raw+'{}'];
  for(const stage of ['kernel','engine','describe'])for(const source of [...mutations,new Uint8Array([0xc0,0xaf])]){
    const f=fixture({editorInput:true}),bytes=typeof source==='string'?encoder.encode(source):source;let cutoff;
    if(stage==='kernel')f.kernel._gui_web_engine_editor_describe_v1=pointer=>{f.kernel.HEAPU8.set(bytes,pointer);cutoff=bootstrapSnapshot(f);return bytes.length;};
    else if(stage==='engine')f.engine._bib_engine_wasm_editor_facts_v1=pointer=>{f.engine.HEAPU8.set(bytes,pointer);cutoff=bootstrapSnapshot(f);return bytes.length;};
    else{const dispatch=f.engine._bib_engine_wasm_dispatch_v1;f.engine._bib_engine_wasm_dispatch_v1=(op,p,n,out,cap)=>{
      if(op!==ENGINE.DESCRIBE)return dispatch(op,p,n,out,cap);const request=decodeRecord(f.engine.HEAPU8.subarray(p,p+n),{receipt:false,maximum:n}),response=receipt(request,{payload:bytes});
      f.engine.HEAPU8.set(response,out);cutoff=bootstrapSnapshot(f);return response.length;
    };}
    await f.send(f.message);assert.equal(f.controller.state,'failed');assert.equal(f.factoryCount,stage==='kernel'?1:2);assert.deepEqual(bootstrapSnapshot(f),cutoff);
    assert.equal(f.kernel.calls.some(value=>value.kind===OP.CONFIGURE),false);assert.equal(f.engine.calls.some(value=>value.kind===ENGINE.START),false);
  }
});
test('editor bootstrap preflights all six exact exports and never substitutes document configure',async()=>{
  for(const name of ['_bib_engine_wasm_bridge_v1','_bib_engine_wasm_dispatch_v1','_bib_engine_wasm_editor_facts_v1','_bib_engine_wasm_editor_configure_v1','_malloc','_free']){
    const f=fixture({editorInput:true});delete f.engine[name];await f.send(f.message);await assertBootstrapStopped(f);
    assert.equal(f.documentBootstrap.configure.length,0);assert.equal(f.documentBootstrap.facts.length,0);assert.equal(f.engine.allocations.length,0);assert.equal(f.engine.freed.length,0);
  }
});
test('editor bootstrap traps or owner loss in facts free configure and marker stop all later exports',async()=>{
  for(const stage of ['facts','free','configure','marker']){
    const f=fixture({editorInput:true});let cutoff;
    const name=stage==='facts'?'_bib_engine_wasm_editor_facts_v1':stage==='free'?'_free':stage==='configure'?'_bib_engine_wasm_editor_configure_v1':'_bib_engine_wasm_bridge_v1',original=f.engine[name];
    f.engine[name]=(...args)=>{if(stage==='marker'&&!f.documentBootstrap.configure.length)return original(...args);cutoff=bootstrapSnapshot(f);throw Error('editor '+stage+' trap');};
    await f.send(f.message);await assertBootstrapStopped(f,cutoff);assert.equal(f.documentBootstrap.configure.length,stage==='marker'?1:0);
  }
});
test('editor owned4095-byte facts survive heap growth and release before exact64-bit configure',async()=>{
  const f=fixture({editorInput:true}),raw=encoder.encode(JSON.stringify(editorProfile())),padded=new Uint8Array(4095).fill(32);padded.set(raw);let scratch;
  const facts=f.engine._bib_engine_wasm_editor_facts_v1;f.engine._bib_engine_wasm_editor_facts_v1=(pointer,capacity)=>{scratch=pointer;f.engine.grow();facts(pointer,capacity);f.engine.HEAPU8.set(padded,pointer);f.engine.grow();return padded.length;};
  f.engine.onFree=pointer=>{if(pointer===scratch){f.engine.HEAPU8.fill(0,pointer,pointer+4096);f.engine.grow();scratch=null;}};
  await f.send(f.message);assert.equal(f.controller.state,'ready');assert.deepEqual(f.documentBootstrap.configure,[{lo:4294967294,hi:4294967295}]);assert.deepEqual(f.documentBootstrap.freedAtConfigure,[1]);
  await f.send({type:'close'});assert.equal(f.controller.state,'closed');
});
test('actual installer keeps Foundation factory options separate from deferred engine host options',async()=>{
  const f=fixture();await f.send(f.message);
  assert.equal(f.controller.state,'ready');
  const byRole=Object.fromEntries(f.loads.map(({role,options})=>[role,options]));
  assert.ok(byRole.kernel&&byRole.engine,'both actual retained factories must be loaded');
  assert.deepEqual(Object.keys(byRole.kernel).sort(),['locateFile','print','printErr','wasmBinary']);
  assert.equal(Object.hasOwn(byRole.kernel,'noInitialRun'),false,
    'Foundation --no-entry factory uses its incoming API without engine-only deferral');
  assert.equal(Object.hasOwn(byRole.kernel,'foundationEngineHost'),false);
  assert.deepEqual(Object.keys(byRole.engine).sort(),
    ['foundationEngineHost','locateFile','noInitialRun','print','printErr','wasmBinary']);
  assert.equal(byRole.engine.noInitialRun,true,'retained engine startup remains deferred');
  assert.equal(typeof byRole.engine.foundationEngineHost,'function');
  for(const options of [byRole.kernel,byRole.engine]){
    assert.ok(options.wasmBinary instanceof Uint8Array);
    assert.equal(typeof options.print,'function');assert.equal(typeof options.printErr,'function');
    assert.equal(typeof options.locateFile,'function');
  }
  assert.equal(f.engine.calls.some(value=>value.kind===ENGINE.START),true,
    'engine deferred-start path must still reach its explicit START');
  await f.send({type:'close'});assert.equal(f.controller.state,'closed');
});
test('editor DESCRIBE must agree with retained and preconfigured facts before Package CONFIGURE',async()=>{
  const changed=editorProfile();changed.build_sha256='9'.repeat(64);const f=fixture({editorInput:true,describedProfile:changed});await f.send(f.message);
  assert.equal(f.controller.state,'failed');assert.equal(f.documentBootstrap.configure.length,1);assert.equal(f.kernel.calls.some(value=>value.kind===OP.CONFIGURE),false);
  assert.deepEqual(f.engine.calls.map(value=>value.kind),[ENGINE.DESCRIBE]);assert.equal(f.engine.calls.some(value=>value.kind===ENGINE.START),false);
});


function deferred(){let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return{promise,resolve,reject};}
async function until(predicate,label){
  for(let count=0;count<128;++count){if(predicate())return;await Promise.resolve();}
  assert.ok(predicate(),'timed out awaiting '+label);
}

test('capture checkpoint null preserves the synchronous configure-to-start phase',async()=>{
  const f=fixture({documentInput:'pixel',captureCheckpoint:null});let startAtConfigureMicrotask=null;
  const dispatch=f.kernel._gui_web_engine_dispatch_v1;
  f.kernel._gui_web_engine_dispatch_v1=(operation,...args)=>{
    const result=dispatch(operation,...args);
    if(operation===OP.CONFIGURE)queueMicrotask(()=>{
      startAtConfigureMicrotask=f.engine.calls.filter(value=>value.kind===ENGINE.START).length;
    });
    return result;
  };
  await f.send(f.message);
  assert.equal(f.controller.state,'ready');
  assert.equal(startAtConfigureMicrotask,1,'null checkpoint must not insert an await after validated CONFIGURE');
  assert.equal(f.engine.calls.filter(value=>value.kind===ENGINE.START).length,1);
});

test('capture checkpoint callback is validated before the Worker message handler is installed',()=>{
  const scope={postMessage(){},close(){}};
  assert.throws(()=>installAppendedEngineWasmWorker(scope,undefined,undefined,undefined,{}),/capture checkpoint/i);
  assert.throws(()=>installAppendedEngineWasmWorker(scope,undefined,undefined,undefined,null,{}),/owner task gate/i);
  assert.equal(Object.hasOwn(scope,'onmessage'),false,'invalid checkpoint must be refused before handler installation');
});

test('capture checkpoint gates inspected and configured startup phases',async()=>{
  const inspected=deferred(),configured=deferred(),phases=[];
  const f=fixture({documentInput:'pixel',captureCheckpoint(phase){
    phases.push(phase);return phase==='inspected'?inspected.promise:configured.promise;
  }});
  const initializing=f.send(f.message);
  await until(()=>phases.length===1,'inspected checkpoint');
  assert.deepEqual(phases,['inspected']);
  assert.equal(f.kernel.calls.filter(value=>value.kind===OP.CONFIGURE).length,0);
  assert.equal(f.engine.calls.filter(value=>value.kind===ENGINE.START).length,0);
  inspected.resolve();
  await until(()=>phases.length===2,'configured checkpoint');
  assert.deepEqual(phases,['inspected','configured']);
  assert.equal(f.kernel.calls.filter(value=>value.kind===OP.CONFIGURE).length,1);
  assert.equal(f.engine.calls.filter(value=>value.kind===ENGINE.START).length,0);
  configured.resolve();await initializing;
  assert.equal(f.controller.state,'ready');
  assert.equal(f.engine.calls.filter(value=>value.kind===ENGINE.START).length,1);
});

test('checkpoint rejection follows existing fail path and prevents later configure or START',async()=>{
  for(const rejectedPhase of ['inspected','configured']){
    const phases=[],f=fixture({documentInput:'pixel',captureCheckpoint(phase){
      phases.push(phase);if(phase===rejectedPhase)throw Error('fixture checkpoint rejected '+phase);
    }});
    await f.send(f.message);
    assert.deepEqual(phases,rejectedPhase==='inspected'?['inspected']:['inspected','configured']);
    assert.equal(f.controller.state,'failed',rejectedPhase);
    assert.equal(f.closed,1,rejectedPhase);
    assert.equal(f.kernel.calls.filter(value=>value.kind===OP.CONFIGURE).length,rejectedPhase==='inspected'?0:1);
    assert.equal(f.engine.calls.filter(value=>value.kind===ENGINE.START).length,0);
    assert.equal(f.posted.filter(value=>value.type==='error').length,1);
    const calls=[f.kernel.calls.length,f.engine.calls.length,f.kernel.exports.length,f.engine.exports.length];
    await f.send(f.message);await f.send({type:'receive',id:1,text:'{}'});
    assert.deepEqual([f.kernel.calls.length,f.engine.calls.length,f.kernel.exports.length,f.engine.exports.length],calls,
      'rejected checkpoint must leave no later native-call authority');
  }
});

test('close while inspected checkpoint is pending prevents configure and START',async()=>{
  const inspected=deferred(),phases=[];
  const f=fixture({documentInput:'pixel',captureCheckpoint(phase){phases.push(phase);return inspected.promise;}});
  const initializing=f.send(f.message);
  await until(()=>phases.length===1,'pending inspected checkpoint');
  await f.send({type:'close'});
  assert.equal(f.kernel.calls.filter(value=>value.kind===OP.CONFIGURE).length,0);
  assert.equal(f.engine.calls.filter(value=>value.kind===ENGINE.START).length,0);
  inspected.resolve();await initializing;
  assert.equal(f.controller.state,'closed');
  assert.equal(f.closed,1);
  assert.deepEqual(phases,['inspected'],'close must prevent entry to configured checkpoint');
  assert.equal(f.kernel.calls.filter(value=>value.kind===OP.CONFIGURE).length,0);
  assert.equal(f.engine.calls.filter(value=>value.kind===ENGINE.START).length,0);
  assert.equal(f.posted.some(value=>value.type==='ready'),false);
});

test('init owner hook receives the actual message and gates ready until its action runs',async()=>{
  const entered=deferred(),release=deferred();let observedMessage,actionRuns=0;
  const f=fixture({beforeOwnerTask:async(action,message)=>{
    observedMessage=message;entered.resolve();await release.promise;action();++actionRuns;
  }});
  const initializing=f.send(f.message);
  await entered.promise;
  assert.strictEqual(observedMessage,f.message,'hook must receive the exact init object submitted to the Worker');
  assert.equal(f.controller.state,'starting');
  assert.equal(f.posted.some(value=>value.type==='ready'),false,'ready must wait for the hook-owned action');
  assert.equal(actionRuns,0);
  release.resolve();await initializing;
  assert.equal(actionRuns,1);
  assert.equal(f.controller.state,'ready');
  assert.equal(f.posted.filter(value=>value.type==='ready').length,1);
  assert.ok(f.kernel.ccalls.some(value=>value.name==='gui_web_create'),'the gated action performs actual ready construction');
  await f.send({type:'close'});assert.equal(f.controller.state,'closed');
});

test('close during init owner gate prevents ready and closes after the gate is released',async()=>{
  const entered=deferred(),release=deferred();let actionRuns=0;
  const f=fixture({beforeOwnerTask:async(action,message)=>{
    assert.strictEqual(message,f.message);entered.resolve();await release.promise;action();++actionRuns;
  }});
  const initializing=f.send(f.message);await entered.promise;
  assert.equal(f.controller.state,'starting');assert.equal(f.posted.some(value=>value.type==='ready'),false);
  await f.send({type:'close'});
  assert.equal(f.controller.state,'closed');assert.equal(f.closed,1);
  assert.equal(f.posted.some(value=>value.type==='ready'),false);
  release.resolve();await initializing;await microtasks();
  assert.equal(actionRuns,1,'the hook action can return, but the closed Worker must reject its ready publication');
  assert.equal(f.controller.state,'closed');assert.equal(f.closed,1);
  assert.equal(f.posted.some(value=>value.type==='ready'),false);
  assert.equal(f.kernel.ccalls.filter(value=>value.name==='gui_web_destroy').length,1);
});
