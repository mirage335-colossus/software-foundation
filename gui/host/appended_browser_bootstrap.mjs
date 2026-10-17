import {createEmbeddedFrontend} from './browser_embedding.mjs';
import {createWasmTransport} from './wasm_transport.mjs';

const MAX_PACKAGE=256*1024*1024,MAX_INDEX=4*1024*1024,MAX_MODULE=4*1024*1024,MAX_KERNEL_WASM=64*1024*1024,TRAILER=192;
const utf8=new TextEncoder(),decoder=new TextDecoder('utf-8',{fatal:true,ignoreBOM:true});
const fail=message=>{throw Error(message);};
const keys=(value,names)=>{
  if(!value||Array.isArray(value)||typeof value!=='object'||Object.keys(value).sort().join('\0')!==[...names].sort().join('\0'))fail('Unexpected appended package fields');
};
const integer=(value,maximum,minimum=0)=>{
  if(!Number.isSafeInteger(value)||value<minimum||value>maximum)fail('Invalid appended package integer');return value;
};
const scalar=value=>{
  if(typeof value!=='string')fail('Invalid appended package text');
  for(let n=0;n<value.length;n++){
    const unit=value.charCodeAt(n);
    if(unit>=0xd800&&unit<=0xdbff){const next=value.charCodeAt(++n);if(!(next>=0xdc00&&next<=0xdfff))fail('Invalid Unicode scalar');}
    else if(unit>=0xdc00&&unit<=0xdfff)fail('Invalid Unicode scalar');
  }
  return value;
};
const canonical=value=>{
  if(value===null||typeof value==='boolean')return JSON.stringify(value);
  if(typeof value==='number'){integer(value,Number.MAX_SAFE_INTEGER);return String(value);}
  if(typeof value==='string')return JSON.stringify(scalar(value));
  if(Array.isArray(value))return '['+value.map(canonical).join(',')+']';
  if(value&&typeof value==='object')return '{'+Object.keys(value).sort().map(key=>JSON.stringify(scalar(key))+':'+canonical(value[key])).join(',')+'}';
  fail('Invalid canonical appended JSON');
};
const hex=bytes=>Array.from(bytes,value=>value.toString(16).padStart(2,'0')).join('');
const sha=async bytes=>hex(new Uint8Array(await globalThis.crypto.subtle.digest('SHA-256',bytes)));
const equal=(left,right)=>left.length===right.length&&left.every((value,n)=>value===right[n]);
const hash=value=>typeof value==='string'&&value.length===64&&/^[0-9a-f]{64}$/.test(value);
const strings=(value,label)=>{
  if(!Array.isArray(value)||value.length>4096||value.some(item=>typeof item!=='string'||!/^[-A-Za-z0-9_.]{1,128}(?![\s\S])/.test(item)||!/^[A-Za-z0-9]/.test(item))||value.join('\0')!==[...new Set(value)].sort().join('\0'))fail('Invalid '+label);
};

export function decodeAppendedBase64(encoded,maximum) {
  if(typeof encoded!=='string'||encoded.length>4*Math.ceil(maximum/3)||encoded.length%4||/[^A-Za-z0-9+/=]/.test(encoded))fail('Invalid appended base64');
  // Avoid repeated regex groups over multi-megabyte kernel assets: Firefox's
  // regex engine can exhaust its stack. The round trip checks exact padding
  // and unused bits after atob validates grammar; the scan rejects whitespace.
  const raw=atob(encoded),bytes=new Uint8Array(raw.length);
  for(let n=0;n<raw.length;n++)bytes[n]=raw.charCodeAt(n);
  if(bytes.length>maximum||btoa(raw)!==encoded)fail('Noncanonical appended base64');return bytes;
}

// The browser has DOM text, not access to the raw source file. prefix is the
// canonical shell reconstructed from retained raw script/style text. This checks
// its consistency with the trailer; the independently pinned Python verifier
// establishes the actual file's exact prefix and suffix bytes before delivery.
export async function verifyAppendedBinary(encoded,prefix,policy) {
  if(encoded===null)return null;
  if(!(prefix instanceof Uint8Array)||!prefix.length||prefix.length>512*1024*1024)fail('Invalid retained browser prefix');
  const bytes=decodeAppendedBase64(encoded,MAX_PACKAGE+TRAILER);
  if(bytes.length<TRAILER)fail('Truncated appended trailer');
  const trailer=bytes.subarray(bytes.length-TRAILER),view=new DataView(trailer.buffer,trailer.byteOffset,trailer.byteLength);
  const u64=offset=>{const value=view.getBigUint64(offset,true);if(value>BigInt(Number.MAX_SAFE_INTEGER))fail('Oversized appended integer');return Number(value);};
  if(decoder.decode(trailer.subarray(0,8))!=='SFAPND01'||view.getUint32(8,true)!==1||view.getUint32(12,true)!==TRAILER||u64(48)!==3||trailer.subarray(152).some(value=>value!==0))fail('Unsupported appended HTML trailer');
  const length=u64(24),offset=u64(32),indexLength=u64(40);
  integer(length,MAX_PACKAGE);integer(offset,length);integer(indexLength,MAX_INDEX,1);
  if(u64(16)!==prefix.length||length!==bytes.length-TRAILER||offset+indexLength!==length||await sha(prefix)!==hex(trailer.subarray(56,88)))fail('Appended browser prefix or lengths differ');
  const packageBytes=bytes.subarray(0,length),indexBytes=bytes.subarray(offset,length);
  if(await sha(packageBytes)!==hex(trailer.subarray(88,120))||await sha(indexBytes)!==hex(trailer.subarray(120,152)))fail('Appended package or index digest differs');
  const source=decoder.decode(indexBytes),index=JSON.parse(source);
  if(!equal(utf8.encode(canonical(index)),indexBytes))fail('Noncanonical appended index');
  keys(index,['schema_version','kind','application','components','requires','identities','files']);
  if(index.schema_version!==1||index.kind!=='foundation-appended-package')fail('Unsupported appended package');
  keys(index.application,['id','name','version']);
  for(const value of Object.values(index.application))if(!scalar(value)||utf8.encode(value).length>256||/[\u0000-\u001f\u007f-\u009f]/.test(value))fail('Invalid application identity');
  if(!/^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)+$/.test(index.application.id)||index.application.version.length>128||!/^\d+\.\d+\.\d+(?:-[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?(?:\+[0-9A-Za-z]+(?:[.-][0-9A-Za-z]+)*)?$/.test(index.application.version))fail('Invalid application identity');
  keys(index.components,['web','binary']);keys(index.components.web,['present','entry']);keys(index.components.binary,['present','entry','profile']);
  if(index.components.web.present!==false||index.components.web.entry!==null)fail('Rich appended web applications are unavailable in this binary kernel');
  if(index.components.binary.present!==true||index.components.binary.entry!=='binary/application.wasm'||index.components.binary.profile!=='foundation-guest-v1')fail('This browser kernel requires one portable binary application');
  keys(index.requires,['abi','services','capabilities']);keys(index.requires.abi,['major','minor']);
  integer(index.requires.abi.major,65535,1);integer(index.requires.abi.minor,65535);
  if(index.requires.abi.major!==policy.abi.major||index.requires.abi.minor>policy.abi.minor)fail('Incompatible application ABI');
  for(const name of ['services','capabilities']){
    strings(index.requires[name],name);
    if(index.requires[name].some(value=>!policy[name].includes(value)))fail('Browser kernel lacks required '+name);
  }
  if(!index.identities||Array.isArray(index.identities)||typeof index.identities!=='object'||Object.keys(index.identities).length>128)fail('Invalid input identities');
  for(const [name,value] of Object.entries(index.identities))if(!/^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}(?![\s\S])/.test(name)||!hash(value))fail('Invalid input identity');
  if(!Array.isArray(index.files)||index.files.length!==1)fail('Binary package must contain exactly one module');
  const entry=index.files[0];keys(entry,['path','component','offset','length','media_type','sha256']);
  integer(entry.length,MAX_MODULE,8);
  if(entry.path!=='binary/application.wasm'||entry.component!=='binary'||entry.media_type!=='application/wasm'||entry.offset!==0||entry.length!==offset||!hash(entry.sha256))fail('Invalid binary component inventory');
  const module=bytes.slice(0,offset);
  if(!equal(module.subarray(0,8),new Uint8Array([0,97,115,109,1,0,0,0]))||await sha(module)!==entry.sha256)fail('Binary module digest or header differs');
  return Object.freeze({module,application:Object.freeze(index.application)});
}

export async function startAppendedBrowser({prefix,kernel,workerSource,host=globalThis}) {
  const status=host.document.querySelector('#status'),mount=host.document.querySelector('#application');
  const report=message=>{status.textContent=message;};
  const urls=[];
  let transport,frontend,closed=false;
  const revoke=()=>{for(const url of urls.splice(0))host.URL.revokeObjectURL(url);};
  const close=()=>{
    if(closed)return;closed=true;host.removeEventListener('pagehide',close);
    frontend?.close();if(transport)transport.close().catch(()=>{});revoke();
  };
  // The owner exists before any asynchronous verification or Worker startup.
  // A late initialization result cannot revive a document that has left.
  host.addEventListener('pagehide',close);
  try {
  const payloads=host.document.querySelectorAll('#foundation-appended-v1');
  if(payloads.length>1)fail('Duplicate appended payload blocks');
  const payload=payloads[0];
  if(payload&&payload.getAttribute('type')!=='application/octet-stream')fail('Invalid appended payload block');
  const application=await verifyAppendedBinary(payload?payload.textContent:null,prefix,kernel.policy);
  if(closed)return Object.freeze({close});
  const notices=host.document.createElement('details'),summary=host.document.createElement('summary'),text=host.document.createElement('pre');
  summary.textContent='Software licenses and notices';
  text.textContent=Object.entries(kernel.notices).map(([name,encoded])=>name+'\n'+decoder.decode(decodeAppendedBase64(encoded,4*1024*1024))).join('\n\n');
  notices.append(summary,text);host.document.body.append(notices);
  if(!application){report('No binary application payload is attached.');close();return Object.freeze({close});}
  host.document.title=application.application.name;
  const local=source=>{const url=host.URL.createObjectURL(new host.Blob([source],{type:'text/javascript'}));urls.push(url);return url;};
    const workerURL=local(workerSource);
    transport=createWasmTransport({workerURL,moduleURL:'embedded',factorySource:decoder.decode(decodeAppendedBase64(kernel.assets['gui_appended_web_wasm.js'],16*1024*1024)),
      wasmBinary:decodeAppendedBase64(kernel.assets['gui_appended_web_wasm.wasm'],MAX_KERNEL_WASM),
      workerFactory:url=>{
        const worker=new host.Worker(url,{type:'classic'}),post=worker.postMessage.bind(worker);
        worker.postMessage=message=>post(message.type==='init'?{...message,appendedModule:application.module}:message);
        return worker;
      }});
    const initialState=await transport.ready;
    if(closed)throw Error('Browser application closed during startup');
    frontend=createEmbeddedFrontend({mount,initialState,exchange:transport.exchange,release:()=>transport.close(),host,status:report});
    await frontend.ready;report(application.application.name);revoke();
    return Object.freeze({close});
  }catch(error){close();if(transport)await transport.close();throw error;}
}
