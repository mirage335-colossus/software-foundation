import {createCopiedEndpoint,createEngineKernelBridge,copyBytes,encodeRecord,validateEngineProfile,validatePhysicalEngineProfile,validateDocumentEngineProfile,validateEditorEngineProfile,decodeEditorEngineFacts,inspectKernelPhysicalProfile,inspectKernelDocumentProfile,inspectKernelEditorProfile,
  OP,MAX_PACKAGE,MAX_SERVICE} from './engine_kernel_bridge.mjs';

const encoder=new TextEncoder(),MAX_FACTORY=16*1048576,MAX_KERNEL=64*1048576,MAX_ENGINE=256*1048576,MAX_OUTPUT=32*1048576;
const bounded=(value,limit)=>typeof value==='string'&&value.length<=limit&&encoder.encode(value).byteLength<=limit;
const uint=(value,maximum)=>Number.isSafeInteger(value)&&value>=0&&value<=maximum;
const wasmLookup=value=>typeof value==='string'&&/^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(value)&&!value.includes('..');
const arrayPrototype=Object.getPrototypeOf(Uint8Array.prototype),
  heapBuffer=Object.getOwnPropertyDescriptor(arrayPrototype,'buffer').get,
  heapLength=Object.getOwnPropertyDescriptor(arrayPrototype,'byteLength').get,
  heapOffset=Object.getOwnPropertyDescriptor(arrayPrototype,'byteOffset').get,
  bufferLength=Object.getOwnPropertyDescriptor(ArrayBuffer.prototype,'byteLength').get,
  arrayTag=Object.prototype.toString;

// Document facts are a flat JSON object of scalar values. Reject duplicate
// decoded keys without imposing a reconstructed whitespace/key-order encoding.
const documentFacts=bytes=>{
  const text=new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(bytes),result={},seen=new Set();
  const string=/"(?:[^"\\\u0000-\u001f]|\\(?:["\\/bfnrt]|u[0-9a-fA-F]{4}))*"/y,
    scalar=/(?:true|false|null|-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?)/y;
  let offset=0;
  const space=()=>{while(offset<text.length&&/[ \t\r\n]/.test(text[offset]))++offset;};
  const token=expression=>{
    expression.lastIndex=offset;const found=expression.exec(text);
    if(!found)throw Error('Invalid engine document facts JSON');offset=expression.lastIndex;return JSON.parse(found[0]);
  };
  space();if(text[offset++]!=='{')throw Error('Invalid engine document facts object');space();
  if(text[offset]!=='}')for(;;){
    const key=token(string);if(seen.has(key))throw Error('Duplicate engine document facts key');seen.add(key);
    space();if(text[offset++]!==':')throw Error('Invalid engine document facts field');space();
    const value=token(text[offset]==='"'?string:scalar);
    Object.defineProperty(result,key,{value,enumerable:true});space();
    if(text[offset]!==',')break;++offset;space();
  }
  if(text[offset++]!=='}')throw Error('Invalid engine document facts field');space();
  if(offset!==text.length)throw Error('Trailing engine document facts JSON');
  return validateDocumentEngineProfile(result);
};

// A separately maintained rich host. The binary-only Worker and accepted
// profiles are unchanged. No engine binding is fabricated when exports lack it.
export function installAppendedEngineWasmWorker(scope,loadModule=url=>import(url),scheduler=globalThis,onDirty=()=>{},captureCheckpoint=null,beforeOwnerTask=null){
  if(typeof onDirty!=='function')throw Error('Invalid engine Worker document observer');
  if(captureCheckpoint!==null&&typeof captureCheckpoint!=='function')throw Error('Invalid engine Worker capture checkpoint');
  if(beforeOwnerTask!==null&&typeof beforeOwnerTask!=='function')throw Error('Invalid private engine Worker owner task gate');
  let state='new',busy=false,closing=false,closingWait=false,physicalInput=false,documentInput=false,editorInput=false,kernelModule=null,engineModule=null,bridge=null,urls=[];
  let documentBootstrapAttempted=false;
  const post=value=>scope.postMessage(value);
  const revoke=()=>{for(const url of urls.splice(0))URL.revokeObjectURL(url);};
  const fail=error=>{
    if(state==='failed'||state==='closed')return;state='failed';
    // A poisoned engine/owner gets no destructor/free/recovery exports.
    revoke();post({type:'error',message:String(error.message||error).slice(0,4096)});scope.close();
  };
  const shutdown=()=>{
    if(state==='closed'||state==='failed')return;closing=true;
    // A posted close cannot interrupt a synchronous engine call on this owner
    // thread. During asynchronous document startup it may cancel readiness now;
    // waiting for the first document would strand close behind that same wait.
    if(busy&&!(bridge&&state==='starting'))return;
    const result=bridge?.close()??{graceful:true};
    if(result.pending){
      if(!closingWait){closingWait=true;bridge.closed.then(receipt=>{
        closingWait=false;if(state==='closed'||state==='failed')return;
        if(!receipt.graceful){fail(Error('Engine cleanup did not finish safely'));return;}
        busy=false;shutdown();
      });}
      return;
    }
    if(!result.graceful){fail(Error('Engine Worker cannot acknowledge a complete safe close'));return;}
    try{if(kernelModule)kernelModule.ccall('gui_web_destroy',null,[],[]);}
    catch(error){fail(error);return;}
    state='closed';busy=false;revoke();post({type:'closed'});scope.close();
  };
  const output=(type,id,text)=>{
    if(!bounded(text,MAX_OUTPUT))throw Error('Engine GUI response exceeds limit');post({type,id,text});
  };
  const sourceURL=source=>{const url=URL.createObjectURL(new Blob([source],{type:'text/javascript'}));urls.push(url);return url;};
  const configureDocumentEngine=(module,profile,workerEpoch,check)=>{
    if(documentBootstrapAttempted)throw Error('Engine document bootstrap already attempted');
    documentBootstrapAttempted=true;
    const capacity=4096,exports={};
    const live=()=>{check();if(closing)throw Error('Document engine bootstrap lost its owner before startup');};
    live();
    // Discover missing exports before consuming the one-shot configuration.
    // Function.length is not the Wasm signature; retained typed scans own that.
    for(const name of ['_bib_engine_wasm_bridge_v1','_bib_engine_wasm_dispatch_v1',
      '_bib_engine_wasm_document_facts_v1','_bib_engine_wasm_document_configure_v1','_malloc','_free']){
      exports[name]=module[name];live();
      if(typeof exports[name]!=='function')throw Error('Retained engine lacks document bootstrap exports; explicit maintenance required');
    }
    const invoke=(name,args=[])=>{live();const result=Reflect.apply(exports[name],module,args);live();return result;};
    if(invoke('_bib_engine_wasm_bridge_v1')!==0)throw Error('Document engine was configured before its actual Worker identity');
    const pointer=invoke('_malloc',[capacity]);
    const memory=()=>{
      const heap=module.HEAPU8;live();
      if(arrayTag.call(heap)!=='[object Uint8Array]')throw Error('Missing private engine document facts memory');
      const buffer=heapBuffer.call(heap),length=bufferLength.call(buffer);
      if(heapOffset.call(heap)!==0||heapLength.call(heap)!==length||!uint(pointer,0xffffffff)||pointer===0
          ||pointer>length||capacity>length-pointer)throw Error('Invalid engine document facts output span');
      return new Uint8Array(buffer,pointer,capacity);
    };
    memory();live();
    const written=invoke('_bib_engine_wasm_document_facts_v1',[pointer,capacity]);
    if(!uint(written,capacity-1)||written===0)throw Error('Retained engine does not provide bounded document facts');
    const bytes=copyBytes(memory().subarray(0,written),capacity);live();
    if(bytes.some(value=>value===0))throw Error('Engine document facts contain a NUL');
    const actual=documentFacts(bytes);
    if(Object.keys(profile).some(key=>actual[key]!==profile[key]))throw Error('Actual engine document facts differ from retained profile');
    // Release only a fully checked facts allocation BEFORE configure. There is
    // deliberately no finally cleanup after malformed output, a trap, callback
    // or uncertain one-shot binding; the failed Worker performs no more exports.
    invoke('_free',[pointer]);
    const result=invoke('_bib_engine_wasm_document_configure_v1',[
      Number(workerEpoch&0xffffffffn),Number(workerEpoch>>32n)]);
    if(result!==0)throw Error('Engine document Worker configuration failed');
    // createCopiedEndpoint subsequently checks the actual configured65536
    // marker, followed by DESCRIBE, before any kernel CONFIGURE or START.
  };
  const configureEditorEngine=(module,profile,workerEpoch,check)=>{
    if(documentBootstrapAttempted)throw Error('Engine editor bootstrap already attempted');
    documentBootstrapAttempted=true;
    const capacity=4096,exports={};
    const live=()=>{check();if(closing)throw Error('Editor engine bootstrap lost its owner before startup');};
    live();
    for(const name of ['_bib_engine_wasm_bridge_v1','_bib_engine_wasm_dispatch_v1',
      '_bib_engine_wasm_editor_facts_v1','_bib_engine_wasm_editor_configure_v1','_malloc','_free']){
      exports[name]=module[name];live();
      if(typeof exports[name]!=='function')throw Error('Retained engine lacks editor bootstrap exports; explicit maintenance required');
    }
    const invoke=(name,args=[])=>{live();const result=Reflect.apply(exports[name],module,args);live();return result;};
    if(invoke('_bib_engine_wasm_bridge_v1')!==0)throw Error('Editor engine was configured before its actual Worker identity');
    const pointer=invoke('_malloc',[capacity]);
    const memory=()=>{
      const heap=module.HEAPU8;live();
      if(arrayTag.call(heap)!=='[object Uint8Array]')throw Error('Missing private engine editor facts memory');
      const buffer=heapBuffer.call(heap),length=bufferLength.call(buffer);
      if(heapOffset.call(heap)!==0||heapLength.call(heap)!==length||!uint(pointer,0xffffffff)||pointer===0
          ||pointer>length||capacity>length-pointer)throw Error('Invalid engine editor facts output span');
      return new Uint8Array(buffer,pointer,capacity);
    };
    memory();live();const written=invoke('_bib_engine_wasm_editor_facts_v1',[pointer,capacity]);
    if(!uint(written,capacity-1)||written===0)throw Error('Retained engine does not provide bounded editor facts');
    const actual=decodeEditorEngineFacts(copyBytes(memory().subarray(0,written),capacity));live();
    if(Object.keys(profile).some(key=>actual[key]!==profile[key]))throw Error('Actual engine editor facts differ from retained profile');
    invoke('_free',[pointer]);
    const result=invoke('_bib_engine_wasm_editor_configure_v1',[Number(workerEpoch&0xffffffffn),Number(workerEpoch>>32n)]);
    if(result!==0)throw Error('Engine editor Worker configuration failed');
  };
  const factory=async(role,source,wasm,wasmName,assets={})=>{
    if(!bounded(source,MAX_FACTORY))throw Error('Invalid retained factory source');
    if(!wasmLookup(wasmName)||Object.hasOwn(assets,wasmName))throw Error('Invalid or colliding own Wasm lookup');
    const wasmURL=URL.createObjectURL(new Blob([wasm],{type:'application/wasm'}));urls.push(wasmURL);
    const {default:create}=await loadModule(sourceURL(source));
    if(typeof create!=='function')throw Error('Missing retained module factory');
    const options={wasmBinary:wasm,print:()=>{},printErr:()=>{},
      locateFile:name=>{
        // Emscripten resolves its own filename eagerly even with wasmBinary.
        // Only exact retained lookups are admitted; never infer a basename.
        if(name===wasmName)return wasmURL;
        if(!Object.hasOwn(assets,name))throw Error('Unretained engine dependency requested');return assets[name];
      }};
    // Foundation is built --no-entry and has a closed Emscripten incoming API.
    // The separate retained engine requires these explicit deferred-host inputs.
    if(role==='engine'){
      options.noInitialRun=true;
      options.foundationEngineHost=(...args)=>{
        if(!bridge){const error=Error('Engine called its host before copied bridge installation');fail(error);throw error;}
        return bridge.callback(...args);
      };
    }
    return create(options);
  };
  scope.onmessage=async event=>{
    const message=event.data;
    try{
      if(!message||typeof message!=='object'||Array.isArray(message))throw Error('Invalid engine Worker message');
      if(message.type==='close'){shutdown();return;}
      if(closing||state==='failed'||state==='closed')return;
      if(busy)throw Error('Engine Worker operation already outstanding');
      if(message.type==='init'){
        if(state!=='new'||typeof message.epoch!=='string'||!message.epoch||message.epoch.length>128)throw Error('Invalid engine Worker initialization');
        state='starting';busy=true;
        editorInput=message.engineProfile?.kind==='foundation-copied-engine-editor-v1';
        documentInput=message.engineProfile?.kind==='foundation-copied-engine-document-v2';
        const profile=editorInput?validateEditorEngineProfile(message.engineProfile):documentInput?validateDocumentEngineProfile(message.engineProfile):
          message.engineProfile?.kind==='foundation-copied-engine-physical-v1'?validatePhysicalEngineProfile(message.engineProfile):validateEngineProfile(message.engineProfile);
        physicalInput=editorInput||profile.kind==='foundation-copied-engine-physical-v1'||documentInput&&profile.capabilities==='2003';
        if(!['web','both'].includes(message.kernelProfile))throw Error('Invalid retained kernel profile');
        if(message.kernelWasmLookup!=='gui_appended_engine_wasm.wasm'||!wasmLookup(message.engineWasmLookup))throw Error('Invalid retained own Wasm lookup');
        if(typeof message.workerEpoch!=='string'||!/^[1-9][0-9]{0,19}$/.test(message.workerEpoch)||BigInt(message.workerEpoch)>(1n<<64n)-1n)throw Error('Invalid Worker identity');
        const workerEpoch=BigInt(message.workerEpoch),kernelBytes=copyBytes(message.wasmBinary,MAX_KERNEL),engineBytes=copyBytes(message.engineWasmBinary,MAX_ENGINE),
          suffix=copyBytes(message.appendedSuffix,MAX_PACKAGE-40);
        if(!uint(message.prefixLength,512*1048576)||message.prefixLength===0||typeof message.prefixSha256!=='string'||!/^[0-9a-f]{64}$/.test(message.prefixSha256))throw Error('Invalid retained HTML boundary');
        const retained={};let assetTotal=0;
        if(!message.engineAssets||Object.getPrototypeOf(message.engineAssets)!==Object.prototype||Object.keys(message.engineAssets).length>128)throw Error('Invalid retained engine asset inventory');
        if(Object.hasOwn(message.engineAssets,message.engineWasmLookup))throw Error('Engine data asset collides with its own Wasm lookup');
        for(const [name,bytes]of Object.entries(message.engineAssets)){
          if(!/^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(name)||name.includes('..'))throw Error('Invalid retained engine asset name');
          const owned=copyBytes(bytes,64*1048576);assetTotal+=owned.byteLength;if(assetTotal>128*1048576)throw Error('Retained engine assets exceed budget');
          const url=URL.createObjectURL(new Blob([owned]));urls.push(url);retained[name]=url;
        }
        // Factories are inert/deferred; inspect actual engine exports/identity
        // BEFORE Package preparation can construct/initialize a portable Module.
        kernelModule=await factory('kernel',message.factorySource,kernelBytes,message.kernelWasmLookup);
        if(state==='failed'||state==='closed')return;
        if(closing){busy=false;shutdown();return;}
        if(typeof kernelModule._gui_web_engine_profile_v1!=='function'||typeof kernelModule.ccall!=='function'
            ||kernelModule.ccall('gui_web_engine_profile_v1','number',[],[])!==(message.kernelProfile==='web'?1:2))
          throw Error('Retained kernel profile differs or lacks its read-only export; explicit maintenance required');
        if(state==='failed'||state==='closed')return;
        const live=()=>{if(state==='failed'||state==='closed'||(documentInput||editorInput)&&!bridge&&closing)throw Error('Read-only kernel facts lost their live owner');};
        // Old retained kernels need no new export. A present export must report
        // the actual additive composition contract before engine construction.
        const compositionName='_gui_web_application_composition_v1';
        if(compositionName in kernelModule){
          const compositionQuery=kernelModule[compositionName];
          if(typeof compositionQuery!=='function')throw Error('Retained kernel composition export is invalid; explicit maintenance required');
          live();const composition=Reflect.apply(compositionQuery,kernelModule,[]);live();
          if(!Number.isInteger(composition)||composition!==(message.kernelProfile==='web'?5:7))
            throw Error('Retained kernel composition query differs; explicit maintenance required');
        }
        if(editorInput)inspectKernelEditorProfile(kernelModule,profile,live);
        else if(documentInput)inspectKernelDocumentProfile(kernelModule,profile,live);
        else if(physicalInput)inspectKernelPhysicalProfile(kernelModule,profile,live);
        if(state==='failed'||state==='closed')return;
        engineModule=await factory('engine',message.engineFactorySource,engineBytes,message.engineWasmLookup,retained);
        if(state==='failed'||state==='closed')return;
        if(closing){busy=false;shutdown();return;}
        const kernel=createCopiedEndpoint(kernelModule,'kernel',live);
        if(editorInput)configureEditorEngine(engineModule,profile,workerEpoch,live);
        else if(documentInput)configureDocumentEngine(engineModule,profile,workerEpoch,live);
        const engine=createCopiedEndpoint(engineModule,'engine',live,editorInput?{editorProfile:profile}:{});
        live();
        bridge=createEngineKernelBridge({kernel,engine,workerEpoch,post:task=>scheduler.setTimeout(task,0),timer:scheduler,
          abandonClosedDocumentOutcomes:true,onFailure:fail,onDirty,beforeOwnerTask});
        bridge.inspect(profile);
        if(captureCheckpoint!==null){
          await captureCheckpoint('inspected');
          if(state==='failed'||state==='closed')return;
          if(closing){busy=false;shutdown();return;}
          if(state!=='starting'||!busy)throw Error('Engine Worker capture checkpoint lost its startup owner');
        }
        const body=new Uint8Array(40+suffix.byteLength),view=new DataView(body.buffer);view.setBigUint64(0,BigInt(message.prefixLength),true);
        for(let i=0;i<32;i++)body[8+i]=parseInt(message.prefixSha256.slice(i*2,i*2+2),16);body.set(suffix,40);
        const metadata=bridge.configure(encodeRecord(OP.CONFIGURE,{worker:workerEpoch,instance:0n,document:0n,generation:0n},body));
        if(!metadata||Object.keys(metadata).sort().join(',')!=='application_name,entry_url,package_sha256'||typeof metadata.application_name!=='string'
            ||typeof metadata.package_sha256!=='string'||!/^[0-9a-f]{64}$/.test(metadata.package_sha256)
            ||typeof metadata.entry_url!=='string'||!metadata.entry_url.startsWith('app://'+metadata.package_sha256+'/web/'))throw Error('Invalid prepared Package metadata');
        if(captureCheckpoint!==null){
          await captureCheckpoint('configured');
          if(state==='failed'||state==='closed')return;
          if(closing){busy=false;shutdown();return;}
          if(state!=='starting'||!busy)throw Error('Engine Worker capture checkpoint lost its startup owner');
        }
        bridge.start(profile,{raster_output:true,width:800,height:600,entry_url:metadata.entry_url,package_sha256:metadata.package_sha256,
          required_capabilities:profile.capabilities,persistence_seed:''});
        await bridge.ready;
        if(state==='failed')return;
        if(closing){busy=false;shutdown();return;}
        const publishReady=()=>{
          if(state==='failed'||state==='closed'||closing)return;
          output('ready',null,kernelModule.ccall('gui_web_create','string',['string'],[message.epoch]));
          state='ready';busy=false;
        };
        if(beforeOwnerTask===null)publishReady();
        else{
          await beforeOwnerTask(publishReady,message);
          if(closing&&state!=='failed'&&state!=='closed'){busy=false;shutdown();return;}
        }
      }else if(message.type==='receive'){
        if(state!=='ready'||!uint(message.id,Number.MAX_SAFE_INTEGER)||message.id===0||!bounded(message.text,MAX_SERVICE))throw Error('Invalid engine GUI request');
        busy=true;
        bridge.advance();if(state==='failed')return;
        const response=kernelModule.ccall('gui_web_receive','string',['string'],[message.text]);
        // Accepted physical values are drained by the normal owner task only
        // after the native receive/publication stack has completely returned.
        if(physicalInput||documentInput||editorInput)bridge.poll();
        output('response',message.id,response);busy=false;
      }else throw Error('Unknown engine Worker command');
    }catch(error){
      busy=false;
      if(closing&&bridge&&bridge.state!=='failed'&&state!=='failed'&&state!=='closed'){shutdown();return;}
      fail(error);
    }
  };
  return Object.freeze({get state(){return state;},close:shutdown,
    replayDocumentCompletion(selector){
      if(state!=='ready'||closing||!bridge)return Promise.reject(Error('Document replay requires a live ready Worker owner'));
      return bridge.replayDocumentCompletion(selector);
    }});
}
if(typeof WorkerGlobalScope!=='undefined'&&globalThis instanceof WorkerGlobalScope)installAppendedEngineWasmWorker(globalThis);
