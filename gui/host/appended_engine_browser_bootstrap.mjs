import {createEmbeddedFrontend} from './browser_embedding.mjs';
import {createWasmTransport} from './wasm_transport.mjs';
import {createHostChannel} from './renderer_channel.mjs';
import {validateSurfaceState,validateSurfaceOperation} from './browser_surface_protocol.mjs';
import * as rendererBundle from './renderer_surface_child_bundle.mjs';
import {decodeAppendedBase64} from './appended_browser_bootstrap.mjs';
import {copyBytes,validateEngineProfile,validatePhysicalEngineProfile,validateDocumentEngineProfile,validateEditorEngineProfile,MAX_SERVICE} from './engine_kernel_bridge.mjs';

const MAX_PREFIX=512*1048576,MAX_PACKAGE=256*1048576,TRAILER=192;
const decoder=new TextDecoder('utf-8',{fatal:true,ignoreBOM:true});
const hex=bytes=>Array.from(bytes,v=>v.toString(16).padStart(2,'0')).join('');
const digest=async bytes=>hex(new Uint8Array(await globalThis.crypto.subtle.digest('SHA-256',bytes)));
const exact=(value,keys)=>value&&Object.getPrototypeOf(value)===Object.prototype&&Object.keys(value).length===keys.length&&keys.every(k=>Object.hasOwn(value,k));
const hash=value=>typeof value==='string'&&/^[0-9a-f]{64}$/.test(value);
const wasmLookup=value=>typeof value==='string'&&/^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(value)&&!value.includes('..');
const rendererFields=['CHILD_SCRIPT','CHILD_SCRIPT_SHA256','CHILD_CSP','CHILD_SANDBOX','CHILD_PROTOCOL','CHILD_STYLE'];
const capturePhysicalRenderer=(value,profile='physical')=>{
  if(!value||typeof value!=='object'||Object.getPrototypeOf(value)!==Object.prototype)throw Error(`Missing retained ${profile} renderer bundle`);
  const descriptors=Object.getOwnPropertyDescriptors(value),keys=Reflect.ownKeys(descriptors);
  if(keys.length!==rendererFields.length||keys.some(key=>typeof key!=='string'||!rendererFields.includes(key)))
    throw Error('Invalid retained physical renderer bundle fields');
  const captured={};
  for(const key of rendererFields){
    const descriptor=descriptors[key];
    if(!descriptor||!Object.hasOwn(descriptor,'value')||typeof descriptor.value!=='string')throw Error('Invalid retained physical renderer bundle data');
    captured[key]=descriptor.value;
  }
  return Object.freeze(captured);
};
const captureEditorProtocol=value=>{
  const names=['validateEditorPublication','validateEditorOperation','validateEditorReply'];
  if(!exact(value,names)||Reflect.ownKeys(value).length!==names.length)throw Error('Missing retained editor channel protocol');
  const captured={};
  for(const name of names){const d=Object.getOwnPropertyDescriptor(value,name);if(!d?.enumerable||!Object.hasOwn(d,'value')||typeof d.value!=='function')throw Error('Invalid retained editor channel protocol');captured[name]=d.value;}
  return Object.freeze(captured);
};

const captureDocumentProtocol=value=>{
  const names=['validateDocumentState','validateDocumentOperation','validateDocumentReply'];
  if(!exact(value,names)||Reflect.ownKeys(value).length!==names.length)throw Error('Invalid retained document channel protocol');
  const captured={};
  for(const name of names){const d=Object.getOwnPropertyDescriptor(value,name);if(!d?.enumerable||!Object.hasOwn(d,'value')||typeof d.value!=='function')throw Error('Invalid retained document channel protocol');captured[name]=d.value;}
  return Object.freeze(captured);
};

// DOM source gives semantic consistency, not access to exact raw HTML bytes.
// The external verifier alone establishes the actual prefix/tail before delivery.
// C++ read_package subsequently validates canonical index and ALL component bytes.
export async function verifyEngineSuffix(encoded,prefix){
  if(encoded===null)return null;
  const retained=copyBytes(prefix,MAX_PREFIX);
  if(!retained.byteLength)throw Error('Missing retained browser prefix');
  const suffix=decodeAppendedBase64(encoded,MAX_PACKAGE+TRAILER);
  if(suffix.byteLength<TRAILER)throw Error('Truncated rich application suffix');
  const offset=suffix.byteLength-TRAILER,trailer=new Uint8Array(suffix.buffer,offset,TRAILER),view=new DataView(trailer.buffer,trailer.byteOffset,trailer.byteLength);
  const length=position=>{const value=view.getBigUint64(position,true);if(value>BigInt(Number.MAX_SAFE_INTEGER))throw Error('Oversized appended boundary');return Number(value);};
  if(decoder.decode(new Uint8Array(trailer.buffer,trailer.byteOffset,8))!=='SFAPND01'||view.getUint32(8,true)!==1||view.getUint32(12,true)!==TRAILER
      ||length(16)!==retained.byteLength||length(24)!==offset||length(24)>MAX_PACKAGE||length(32)+length(40)!==offset
      ||length(40)===0||length(40)>4*1048576||length(48)!==3||trailer.subarray(152).some(v=>v!==0))throw Error('Invalid rich HTML carrier trailer');
  const prefixSha256=await digest(retained);
  if(prefixSha256!==hex(trailer.subarray(56,88))||await digest(suffix.subarray(0,offset))!==hex(trailer.subarray(88,120))
      ||await digest(suffix.subarray(length(32),offset))!==hex(trailer.subarray(120,152)))throw Error('Appended rich package/boundary digest differs');
  return Object.freeze({suffix,prefixLength:retained.byteLength,prefixSha256});
}

// A new explicit rich producer supplies this exact base-owned asset schema.
// No entry is interpreted as an application script or fetched from a URL.
async function asset(value,maximum){
  if(!exact(value,['data','sha256'])||!hash(value.sha256))throw Error('Invalid retained asset descriptor');
  const bytes=decodeAppendedBase64(value.data,maximum);
  if(await digest(bytes)!==value.sha256)throw Error('Retained asset digest differs');return bytes;
}
export async function startAppendedEngineBrowser({prefix,kernel,workerSource,physicalRendererBundle=null,editorRendererBundle=null,editorProtocol=null,documentProtocol=null,host=globalThis}){
  const editorInput=kernel?.kind==='foundation-copied-engine-editor-browser';
  const documentInput=kernel?.kind==='foundation-copied-engine-document-browser';
  const physicalInput=kernel?.kind==='foundation-copied-engine-physical-browser'||documentInput&&kernel?.engine_profile?.document_profile==='foundation-engine-copied2003-ndv2-v1';
  // The physical producer supplies a six-field data projection of its reviewed
  // module. Capture owned primitive values before touching DOM or Worker state.
  const capturedPhysicalRenderer=physicalInput?capturePhysicalRenderer(physicalRendererBundle):null;
  const capturedEditorRenderer=editorInput?capturePhysicalRenderer(editorRendererBundle,'editor'):null;
  const selectedEditorProtocol=editorInput?captureEditorProtocol(editorProtocol):null;
  const selectedDocumentProtocol=documentProtocol===null?null:captureDocumentProtocol(documentProtocol);
  const status=host.document.querySelector('#status'),mount=host.document.querySelector('#application');
  if(!status||!mount)throw Error('Missing retained browser mounts');
  let closed=false,transport=null,frontend=null;const urls=[];
  const report=message=>{status.textContent=String(message);};
  const revoke=()=>{for(const url of urls.splice(0))host.URL.revokeObjectURL(url);};
  const close=()=>{if(closed)return;closed=true;host.removeEventListener('pagehide',close);frontend?.close();transport?.close().catch(()=>{});revoke();};
  host.addEventListener('pagehide',close);
  try{
    if(!exact(kernel,['schema_version','kind','kernel_profile','kernel_wasm_lookup','engine_wasm_lookup','kernel_factory','kernel_wasm','engine_factory','engine_wasm','engine_profile','engine_assets','notices'])
        ||kernel.schema_version!==1||!['foundation-copied-engine-browser','foundation-copied-engine-physical-browser','foundation-copied-engine-document-browser','foundation-copied-engine-editor-browser'].includes(kernel.kind)||!['web','both'].includes(kernel.kernel_profile)
        ||kernel.kernel_wasm_lookup!=='gui_appended_engine_wasm.wasm'||!wasmLookup(kernel.engine_wasm_lookup))throw Error('Unsupported retained rich browser descriptor');
    const profile=editorInput?validateEditorEngineProfile(kernel.engine_profile):documentInput?validateDocumentEngineProfile(kernel.engine_profile):physicalInput?validatePhysicalEngineProfile(kernel.engine_profile):validateEngineProfile(kernel.engine_profile);
    // Only the separately verified physical producer injects this reviewed
    // pure-data renderer variant. Its absence cannot select legacy capture.
    const selectedRenderer=editorInput?capturedEditorRenderer:physicalInput?capturedPhysicalRenderer:rendererBundle;
    const payloads=host.document.querySelectorAll('#foundation-appended-v1');
    if(payloads.length>1||payloads.length&&payloads[0].getAttribute('type')!=='application/octet-stream')throw Error('Invalid inert appended payload block');
    const prepared=await verifyEngineSuffix(payloads.length?payloads[0].textContent:null,prefix);
    if(closed)return Object.freeze({close});
    if(!prepared){report('No appended application payload is attached.');close();return Object.freeze({close});}
    const factory=decoder.decode(await asset(kernel.kernel_factory,16*1048576)),wasm=await asset(kernel.kernel_wasm,64*1048576),
      engineFactory=decoder.decode(await asset(kernel.engine_factory,16*1048576)),engineWasm=await asset(kernel.engine_wasm,256*1048576);
    const assets={};let total=0;
    if(!kernel.engine_assets||Object.getPrototypeOf(kernel.engine_assets)!==Object.prototype||Object.keys(kernel.engine_assets).length>128)throw Error('Invalid engine asset closure');
    for(const [name,value]of Object.entries(kernel.engine_assets)){
      if(!/^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(name)||name.includes('..'))throw Error('Invalid engine asset name');
      if(name===kernel.engine_wasm_lookup)throw Error('Engine data asset collides with its own Wasm lookup');
      const bytes=await asset(value,64*1048576);total+=bytes.byteLength;if(total>128*1048576)throw Error('Engine assets exceed profile');assets[name]=bytes;
    }
    if(!kernel.notices||Object.getPrototypeOf(kernel.notices)!==Object.prototype||Object.keys(kernel.notices).length>128)throw Error('Invalid notices');
    const texts=[];let noticeBytes=0;
    for(const [name,value]of Object.entries(kernel.notices)){
      if(typeof name!=='string'||name.length>256)throw Error('Invalid notice name');
      const bytes=await asset(value,4*1048576);noticeBytes+=bytes.byteLength;if(noticeBytes>16*1048576)throw Error('Notices exceed profile');texts.push(name+'\n'+decoder.decode(bytes));
    }
    if(closed)return Object.freeze({close});
    const details=host.document.createElement('details'),summary=host.document.createElement('summary'),text=host.document.createElement('pre');
    summary.textContent='Software licenses and notices';text.textContent=texts.join('\n\n');details.append(summary,text);host.document.body.append(details);
    if(typeof workerSource!=='string'||workerSource.length>MAX_SERVICE)throw Error('Invalid retained engine Worker source');
    const workerURL=host.URL.createObjectURL(new host.Blob([workerSource],{type:'text/javascript'}));urls.push(workerURL);
    const random=new Uint32Array(2);host.crypto.getRandomValues(random);let epoch=(BigInt(random[0])<<32n)|BigInt(random[1]);if(epoch===0n)epoch=1n;
    transport=createWasmTransport({workerURL,moduleURL:'embedded-engine-kernel',factorySource:factory,wasmBinary:wasm,closeTimeout:10000,
      workerFactory:url=>{
        const worker=new host.Worker(url,{type:'module'}),post=worker.postMessage.bind(worker);
        worker.postMessage=message=>post(message.type==='init'?{...message,workerEpoch:String(epoch),kernelProfile:kernel.kernel_profile,
          kernelWasmLookup:kernel.kernel_wasm_lookup,engineWasmLookup:kernel.engine_wasm_lookup,engineProfile:profile,engineFactorySource:engineFactory,
          engineWasmBinary:engineWasm,engineAssets:assets,appendedSuffix:prepared.suffix,prefixLength:prepared.prefixLength,prefixSha256:prepared.prefixSha256}:message);
        return worker;
      }});
    const initial=await transport.ready;if(closed)return Object.freeze({close});
    const title=initial?.snapshot?.title;if(typeof title!=='string')throw Error('Invalid initial application title');
    host.document.title=title;report(title);
    const surfaceProtocol=physicalInput||editorInput?{
      validateSurfaceState:(snapshot,surface)=>validateSurfaceState(snapshot,surface,editorInput?'editor_v1':'mouse_v1'),
      validateSurfaceOperation:(operation,snapshot,surface)=>validateSurfaceOperation(operation,snapshot,surface,editorInput?'editor_v1':'mouse_v1')
    }:{validateSurfaceState,validateSurfaceOperation};
    frontend=createEmbeddedFrontend({mount,initialState:initial,exchange:value=>transport.exchange(value),release:()=>transport.close(),host,status:report,
      channelFactory:options=>createHostChannel({...options,surfaceProtocol,...(editorInput?{editorProtocol:selectedEditorProtocol}:{}),...(selectedDocumentProtocol?{documentProtocol:selectedDocumentProtocol}:{})}),rendererBundle:selectedRenderer});
    await frontend.ready;if(closed)return Object.freeze({close});return Object.freeze({close,frontend});
  }catch(error){report(error.message||error);close();throw error;}
}
