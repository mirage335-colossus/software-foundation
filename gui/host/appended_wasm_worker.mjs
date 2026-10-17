import {installWasmWorker} from './wasm_worker.mjs';

// This private adapter extends initialization only. The established Worker owns
// ordering, bounded messages, shutdown and the generic GUI create/receive API.
export function installAppendedWasmWorker(scope,loadModule) {
  let moduleBytes=null,initialized=false;
  const bridge={postMessage:message=>scope.postMessage(message),close:()=>scope.close(),onmessage:null};
  installWasmWorker(bridge,async url=>{
    if(!(moduleBytes instanceof Uint8Array)||!(moduleBytes.buffer instanceof ArrayBuffer)||moduleBytes.byteLength<8||moduleBytes.byteLength>4*1024*1024)
      throw Error('Missing or oversized appended binary module');
    // Copy only after bounds validation, inside the established Worker's
    // caught async initialization path. Shared buffers are not a transport.
    moduleBytes=moduleBytes.slice();
    const {default:createModule}=await loadModule(url);
    return {default:async options=>{
      const module=await createModule(options);
      let pointer=0;
      try {
        pointer=module._malloc(moduleBytes.byteLength);
        if(!Number.isSafeInteger(pointer)||pointer<=0||!(module.HEAPU8 instanceof Uint8Array)||pointer>module.HEAPU8.byteLength-moduleBytes.byteLength)
          throw Error('Could not allocate appended module memory');
        try {
          module.HEAPU8.set(moduleBytes,pointer);
          const error=module.ccall('gui_web_prepare','string',['number','number'],[pointer,moduleBytes.byteLength]);
          if(error)throw Error(error);
          return module;
        }finally{module._free(pointer);}
      }catch(error){
        try{module.ccall('gui_web_destroy',null,[],[]);}catch{/* Preserve preparation failure. */}
        throw error;
      }finally{
        moduleBytes=null;
      }
    }};
  });
  scope.onmessage=event=>{
    if(event.data?.type==='init'&&!initialized){
      initialized=true;
      moduleBytes=event.data.appendedModule;
    }
    return bridge.onmessage(event);
  };
}
if(typeof WorkerGlobalScope!=='undefined'&&globalThis instanceof WorkerGlobalScope)
  installAppendedWasmWorker(globalThis,url=>import(url));
