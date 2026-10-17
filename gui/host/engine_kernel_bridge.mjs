// Private neutral transport; application code runs only in the retained engine.
// Constants mirror shared/appended_engine_abi.h, never a native struct layout.
export const BRIDGE_VERSION=0x10000,HEADER_BYTES=72,RECEIPT_BYTES=80;
export const MAX_SERVICE=1048576,MAX_FRAME=16*1048576+48,MAX_PACKAGE=256*1048576+232;
export const DOCUMENT_WORK_PREFIX=56,DOCUMENT_BEGIN_BYTES=16,DOCUMENT_RESULT_PREFIX=40,MAX_DOCUMENT_RESULT=MAX_SERVICE+DOCUMENT_RESULT_PREFIX;
export const EDITOR_WORK_PREFIX=56,EDITOR_BEGIN_BYTES=16,EDITOR_RESULT_PREFIX=40,MAX_EDITOR_RESULT=MAX_SERVICE+EDITOR_RESULT_PREFIX;
export const OP=Object.freeze({CONFIGURE:1,TURN_ENTER:2,TURN_LEAVE:3,BEGIN_DOCUMENT:4,CLOSE_DOCUMENT:5,
  SUBMIT:6,CANCEL:7,STAGE_ACK:8,RESOURCE_RESOLVE:9,RESOURCE_READ:10,RESOURCE_RELEASE:11,
  PUMP_ONE:12,PEEK_DELIVERY:13,PEEK_ACK_RECEIPT:14,PEEK_INPUT:15,DELIVERY_RESULT:16,
  ACK_RECEIPT_RESULT:17,FRAME_COMMIT:18,COMMAND_RESULT:19,CLOSE:20,
  BEGIN_RESOURCE_EPOCH:21,RETIRE_RESOURCE_EPOCH:22,PEEK_RETIRED_DOCUMENT:23,
  RETIRED_DOCUMENT_RESULT:24,PEEK_RETIREMENT_AUDIT:25,RETIREMENT_AUDIT_RESULT:26,
  PEEK_DOCUMENT_WORK:27,DOCUMENT_WORK_RESULT:28,BEGIN_DOCUMENT_WORK:29,
  PEEK_EDITOR_WORK:30,EDITOR_WORK_RESULT:31,BEGIN_EDITOR_WORK:32});
export const ENGINE=Object.freeze({DESCRIBE:0,START:1,ADVANCE:2,CURRENT_DOCUMENT:3,COMMAND:4,QUERY:5,
  DELIVER_SERVICES:6,COLLECT_ACK:7,DISPOSE_RETIRED:8});
export const CONTROL=Object.freeze({OK:0,EMPTY:1,INVALID:2,STALE:3,LIMIT:4,CONFLICT:5,CLOSED:6,UNSUPPORTED:7,INTERNAL:8});
export const RESULT=Object.freeze({ACCEPTED:1,REJECTED:2,RETRY:3,ABANDONED:4});
export const HOST=Object.freeze({WAKE:256,TIMER:257,PERSISTENCE:258});
const ByteArray=Uint8Array,BufferType=ArrayBuffer;
const typed=Object.getPrototypeOf(ByteArray.prototype),get=name=>Object.getOwnPropertyDescriptor(typed,name).get;
const getLength=get('byteLength'),getOffset=get('byteOffset'),getBuffer=get('buffer'),getTag=get(Symbol.toStringTag);
const set=Function.call.bind(ByteArray.prototype.set),encoder=new TextEncoder(),decoder=new TextDecoder('utf-8',{fatal:true,ignoreBOM:true});
const U64_MAX=(1n<<64n)-1n,integer=(v,max=0xffffffff)=>Number.isSafeInteger(v)&&v>=0&&v<=max;
export class BridgeError extends Error {
  constructor(message,{terminal=false,code=null}={}){super(message);this.terminal=terminal;this.code=code;}
}
export const u64=value=>typeof value==='bigint'&&value>=0n&&value<=U64_MAX;
export function copyBytes(value,maximum=MAX_SERVICE){
  let length,offset,buffer;
  try{if(getTag.call(value)!=='Uint8Array')throw Error();length=getLength.call(value);offset=getOffset.call(value);buffer=getBuffer.call(value);}
  catch{throw new BridgeError('Expected owned byte input');}
  if(!(buffer instanceof BufferType)||length>maximum)throw new BridgeError('Shared or oversized bridge bytes');
  const output=new ByteArray(length);set(output,new ByteArray(buffer,offset,length));return output;
}
export function encodeRecord(kind,identity,payload=new ByteArray(),{source=0,transfer=0n,editorProfile=null}={}){
  if(!integer(kind,65535)||!integer(source,2)||!u64(transfer))throw new BridgeError('Invalid copied record kind/source/transfer');
  for(const key of ['worker','instance','document','generation'])if(!u64(identity[key]))throw new BridgeError('Invalid copied u64 identity');
  if(identity.worker===0n)throw new BridgeError('Worker epoch must be nonzero');
  const editor=editorProfile===null?null:validateEditorEngineProfile(editorProfile);
  const body=copyBytes(payload,kind===OP.CONFIGURE?MAX_PACKAGE:kind===OP.FRAME_COMMIT?MAX_FRAME:
    kind===OP.DOCUMENT_WORK_RESULT?MAX_DOCUMENT_RESULT:kind===OP.EDITOR_WORK_RESULT?MAX_EDITOR_RESULT:
    kind===ENGINE.COMMAND&&editor&&editorCommandPrefix(payload,identity)?MAX_SERVICE+56:MAX_SERVICE);
  const bytes=new ByteArray(HEADER_BYTES+body.byteLength),view=new DataView(bytes.buffer);
  set(bytes,new ByteArray([70,75,66,49]));view.setUint16(4,1,true);view.setUint16(6,kind,true);view.setUint32(8,bytes.byteLength,true);
  ['worker','instance','document','generation'].forEach((key,index)=>view.setBigUint64(16+8*index,identity[key],true));
  view.setBigUint64(48,transfer,true);view.setUint32(56,source,true);view.setUint32(64,body.byteLength,true);set(bytes,body,HEADER_BYTES);return bytes;
}
export function decodeRecord(input,{kind,maximum=MAX_SERVICE+RECEIPT_BYTES,receipt=true,worker}={}){
  const bytes=copyBytes(input,maximum);
  if(bytes.byteLength<(receipt?RECEIPT_BYTES:HEADER_BYTES))throw new BridgeError('Truncated bridge record',{terminal:true});
  const view=new DataView(bytes.buffer),observedKind=view.getUint16(6,true);
  if(![70,75,66,49].every((v,i)=>bytes[i]===v)||view.getUint16(4,true)!==1||view.getUint32(8,true)!==bytes.byteLength
      ||view.getUint32(12,true)||view.getUint32(60,true)||view.getUint32(68,true)
      ||view.getUint32(64,true)!==bytes.byteLength-HEADER_BYTES||view.getUint32(56,true)>2
      ||kind!==undefined&&observedKind!==(receipt?kind|0x8000:kind))throw new BridgeError('Malformed copied record',{terminal:true});
  const identity={worker:view.getBigUint64(16,true),instance:view.getBigUint64(24,true),document:view.getBigUint64(32,true),generation:view.getBigUint64(40,true)};
  if(identity.worker===0n||worker!==undefined&&identity.worker!==worker)throw new BridgeError('Wrong Worker epoch',{terminal:true});
  const result={kind:observedKind,identity,transfer:view.getBigUint64(48,true),source:view.getUint32(56,true),
    payload:copyBytes(new ByteArray(bytes.buffer,receipt?RECEIPT_BYTES:HEADER_BYTES,bytes.byteLength-(receipt?RECEIPT_BYTES:HEADER_BYTES)),maximum)};
  if(receipt){result.control=view.getUint32(72,true);result.service=view.getUint32(76,true);
    if(result.control>CONTROL.INTERNAL||result.service>14)throw new BridgeError('Unknown reply status domain',{terminal:true});}
  return result;
}
export const jsonBytes=value=>encoder.encode(JSON.stringify(value));
export const decodeJSON=bytes=>JSON.parse(decoder.decode(copyBytes(bytes,MAX_SERVICE)));
export function scalar32(value){if(!integer(value))throw new BridgeError('Invalid u32');const b=new ByteArray(4);new DataView(b.buffer).setUint32(0,value,true);return b;}
export function scalar64(value){if(!u64(value))throw new BridgeError('Invalid u64');const b=new ByteArray(8);new DataView(b.buffer).setBigUint64(0,value,true);return b;}

// Every pointer belongs to this endpoint only. No borrowed view crosses an
// allocation, export invocation or yield. A trap poisons it before any cleanup.
export function createCopiedEndpoint(module,role,liveness=()=>{},{editorProfile=null}={}){
  if(!['kernel','engine'].includes(role))throw new BridgeError('Unknown endpoint role');
  const admittedEditor=editorProfile===null?null:validateEditorEngineProfile(editorProfile);
  const marker=role==='kernel'?'_gui_web_engine_bridge_v1':'_bib_engine_wasm_bridge_v1';
  const entry=role==='kernel'?'_gui_web_engine_dispatch_v1':'_bib_engine_wasm_dispatch_v1';
  let poisoned=false;
  const poison=error=>{poisoned=true;throw new BridgeError(String(error.message||error),{terminal:true});};
  const heap=()=>{
    let buffer;try{const value=module.HEAPU8;if(getTag.call(value)!=='Uint8Array')throw Error();buffer=getBuffer.call(value);}catch{return poison(Error('Missing current module memory'));}
    if(!(buffer instanceof BufferType))return poison(Error('Shared module memory is unsupported'));
    return new ByteArray(buffer);
  };
  const span=(pointer,length)=>{
    const memory=heap();
    if(!integer(pointer)||!integer(length)||pointer>memory.byteLength||length>memory.byteLength-pointer)return poison(Error('Invalid local module span'));
    return new ByteArray(memory.buffer,pointer,length);
  };
  if(typeof module[marker]!=='function'||typeof module[entry]!=='function'||typeof module._malloc!=='function'||typeof module._free!=='function')throw new BridgeError('Retained '+role+' lacks the copied bridge; explicit maintenance required');
  try{liveness();if(module[marker]()!==BRIDGE_VERSION)throw Error('Incompatible copied bridge version');liveness();heap();liveness();}catch(error){return poison(error);}
  return Object.freeze({module,role,get poisoned(){return poisoned;},get memory(){return heap().buffer;},
    validateSpan(pointer,length){if(poisoned)throw new BridgeError('Endpoint is poisoned',{terminal:true});span(pointer,length);},
    read(pointer,length,maximum=MAX_SERVICE+HEADER_BYTES){if(poisoned)throw new BridgeError('Endpoint is poisoned',{terminal:true});if(!integer(length,maximum))throw new BridgeError('Copied input exceeds operation limit');return copyBytes(span(pointer,length),maximum);},
    write(pointer,capacity,bytes){if(poisoned)throw new BridgeError('Endpoint is poisoned',{terminal:true});const owned=copyBytes(bytes,MAX_FRAME+HEADER_BYTES);if(!integer(capacity)||owned.byteLength>capacity)throw new BridgeError('Engine callback reply space is too small',{terminal:true});set(span(pointer,capacity),owned);return owned.byteLength;},
    call(operation,input,capacity=MAX_SERVICE+RECEIPT_BYTES,validate=()=>{},beforeEntry=()=>{},check=()=>{}){
      if(poisoned)throw new BridgeError('Endpoint is poisoned',{terminal:true});
      const live=()=>{liveness();check();};
      try{live();}catch(error){return poison(error);}
      if(!integer(operation,65535)||!integer(capacity,MAX_FRAME+RECEIPT_BYTES)||capacity<RECEIPT_BYTES)throw new BridgeError('Invalid operation reply capacity');
      const maximum=role==='kernel'&&operation===OP.CONFIGURE?MAX_PACKAGE:role==='kernel'&&operation===OP.FRAME_COMMIT?MAX_FRAME:
        role==='kernel'&&operation===OP.DOCUMENT_WORK_RESULT?MAX_DOCUMENT_RESULT:
        role==='kernel'&&operation===OP.EDITOR_WORK_RESULT?MAX_EDITOR_RESULT:
        role==='engine'&&admittedEditor&&operation===ENGINE.COMMAND&&editorCommandRecord(input)?MAX_SERVICE+56:MAX_SERVICE;
      const bytes=copyBytes(input,maximum+HEADER_BYTES),allocations=[];
      if(bytes.byteLength<HEADER_BYTES)throw new BridgeError('Truncated operation input');
      const worker=new DataView(bytes.buffer).getBigUint64(16,true);
      const allocate=length=>{
        let pointer;try{pointer=module._malloc(length);}catch(error){return poison(error);}
        try{live();}catch(error){return poison(error);}
        if(pointer===0)throw new BridgeError('Bridge allocation refused',{code:CONTROL.LIMIT});
        span(pointer,length);allocations.push(pointer);return pointer;
      };
      try{
        const output=allocate(capacity),pointer=allocate(bytes.byteLength);
        if(pointer<output+capacity&&output<pointer+bytes.byteLength)return poison(Error('Allocator returned overlapping spans'));
        set(span(pointer,bytes.byteLength),bytes);
        // Document claims occur only after both complete local allocations and
        // the input copy exist, immediately before the single provider export.
        try{beforeEntry();live();}catch(error){return poison(error);}
        let written;try{written=module[entry](operation,pointer,bytes.byteLength,output,capacity);}catch(error){return poison(error);}
        try{live();}catch(error){return poison(error);}
        if(integer(written,capacity)){
          const copied=copyBytes(span(output,written),capacity);
          // A complete terminal outcome may still be copied to the other
          // owner. Its validator returns false to forbid even cleanup exports.
          try{const reply=decodeRecord(copied,{kind:operation,worker,maximum:capacity});if(validate(reply)===false)poisoned=true;}catch(error){return poison(error);}
          return copied;
        }
        if([-1,-2,-3].includes(written))throw new BridgeError('Copied operation rejected',{code:written});
        return poison(Error('Copied operation failed or returned malformed output'));
      }finally{
        if(!poisoned)for(const pointer of allocations.reverse()){
          try{module._free(pointer);live();}catch(error){poison(error);}
        }
      }
    }
  });
}

const CALLBACK_OPS=new Set([OP.TURN_ENTER,OP.TURN_LEAVE,OP.BEGIN_DOCUMENT,OP.CLOSE_DOCUMENT,OP.SUBMIT,OP.CANCEL,
  OP.STAGE_ACK,OP.RESOURCE_RESOLVE,OP.RESOURCE_READ,OP.RESOURCE_RELEASE,OP.FRAME_COMMIT,OP.BEGIN_RESOURCE_EPOCH,OP.RETIRE_RESOURCE_EPOCH]);
const hash=value=>typeof value==='string'&&/^[0-9a-f]{64}$/.test(value);
export function validateEngineProfile(value){
  const fields=['schema_version','kind','target','binding','pointer_bits','pthread','shared_memory','bridge_abi','capabilities','contract_sha256','build_sha256','source_recipe_sha256'];
  if(!value||Object.getPrototypeOf(value)!==Object.prototype||Object.keys(value).length!==fields.length||fields.some(k=>!Object.hasOwn(value,k))
      ||value.schema_version!==1||value.kind!=='foundation-copied-engine-v1'||value.target!=='browser-wasm32'
      ||value.binding!=='copied-owner-bridge/direct-worker-v1'||value.pointer_bits!==32||value.pthread!==false||value.shared_memory!==false
      ||value.bridge_abi!==BRIDGE_VERSION||typeof value.capabilities!=='string'||!/^(0|[1-9][0-9]{0,19})$/.test(value.capabilities)
      ||!u64(BigInt(value.capabilities))||BigInt(value.capabilities)!==259n
      ||!['contract_sha256','build_sha256','source_recipe_sha256'].every(k=>hash(value[k])))throw new BridgeError('Unsupported retained engine owner/profile/identity; direct non-pthread Worker binding is required');
  return Object.freeze({...value});
}

// Physical input belongs to a separately retained generation. In particular,
// this does not expand the copied259 profile or its empty command catalog.
export function validatePhysicalEngineProfile(value){
  const fields=['schema_version','kind','target','binding','pointer_bits','pthread','shared_memory','bridge_abi','capabilities',
    'contract_sha256','build_sha256','source_recipe_sha256','command_catalog_sha256','surface_protocol_version','surface_capabilities',
    'mouse_input_version','key_mapping_version','viewport_width','viewport_height','display_scale'];
  if(!value||Object.getPrototypeOf(value)!==Object.prototype||Object.keys(value).length!==fields.length||fields.some(k=>!Object.hasOwn(value,k))
      ||value.schema_version!==1||value.kind!=='foundation-copied-engine-physical-v1'||value.target!=='browser-wasm32'
      ||value.binding!=='copied-owner-bridge/direct-worker-physical-v1'||value.pointer_bits!==32||value.pthread!==false||value.shared_memory!==false
      ||value.bridge_abi!==BRIDGE_VERSION||value.capabilities!=='467'||value.surface_protocol_version!==1||value.surface_capabilities!=='8225'
      ||value.mouse_input_version!==1||value.key_mapping_version!==1||value.viewport_width!==800||value.viewport_height!==600||value.display_scale!==1
      ||value.command_catalog_sha256!=='d244e6a17561b49b937ad25058f2d662f4f86063633b716bdb87d0250796a47b'
      ||!['contract_sha256','build_sha256','source_recipe_sha256','command_catalog_sha256'].every(k=>hash(value[k])))
    throw new BridgeError('Unsupported retained physical engine profile/identity');
  return Object.freeze({...value});
}
const DOCUMENT_PINS=Object.freeze({
  contract_sha256:'aba7800e6aab1898f3614f0b1ac53e59b9f622bf1e9d3a413f50d672a3662298',
  base_header_sha256:'a8e89da85d34b29a4d1bc454495791fa604b81e3477e48ce8ca902e4333a9c0d',
  extension_header_sha256:'7b047bae4d0072ef156ea94ba637566d563fea3a95d43c4c6314afc919b1d626',
  document_catalog_sha256:'6e555d4c3bb71fbc965e1ca49671fab64d744913e18f45b9ba273505e0c6bcf5',
  document_schema_sha256:'f11fd061350f8d663dbcdec7cf0a063e4fb0ff3564d285076690f58e8a84143d',
  action_ack_schema_sha256:'1eb6c2d4f56acebc1423d9e2b5bf9a1717a99963a5c3f11f4b9d7b0fe33b50f5'});
const PHYSICAL_CATALOG='d244e6a17561b49b937ad25058f2d662f4f86063633b716bdb87d0250796a47b';
// These source contracts do not enable a retained provider. Both actual compiled
// kernel facts and engine DESCRIBE must match before Package preparation.
export function validateDocumentEngineProfile(value){
  const physical=value?.document_profile==='foundation-engine-copied2003-ndv2-v1';
  const fields=['schema_version','kind','target','binding','pointer_bits','pthread','shared_memory','bridge_abi','capabilities',
    'contract_sha256','build_sha256','source_recipe_sha256','provider_abi_major','provider_abi_minor','host_abi_major','host_abi_minor',
    'document_profile','base_header_sha256','extension_header_sha256','document_catalog_sha256','document_schema_sha256',
    'action_ack_schema_sha256','viewport_width','viewport_height'];
  if(physical)fields.push('command_catalog_sha256','surface_protocol_version','surface_capabilities','mouse_input_version','key_mapping_version','display_scale');
  if(!value||Object.getPrototypeOf(value)!==Object.prototype||Object.keys(value).length!==fields.length||fields.some(k=>!Object.hasOwn(value,k))
      ||value.schema_version!==1||value.kind!=='foundation-copied-engine-document-v2'||value.target!=='browser-wasm32'
      ||value.binding!=='copied-owner-bridge/direct-worker-document-v2'||value.pointer_bits!==32||value.pthread!==false||value.shared_memory!==false
      ||value.bridge_abi!==BRIDGE_VERSION||value.provider_abi_major!==1||value.provider_abi_minor!==1||value.host_abi_major!==1||value.host_abi_minor!==0
      ||value.document_profile!==(physical?'foundation-engine-copied2003-ndv2-v1':'foundation-engine-copied1795-ndv2-v1')
      ||value.capabilities!==(physical?'2003':'1795')||value.viewport_width!==800||value.viewport_height!==600
      ||Object.keys(DOCUMENT_PINS).some(key=>value[key]!==DOCUMENT_PINS[key])
      ||!['build_sha256','source_recipe_sha256'].every(key=>hash(value[key])&&value[key]!=='0'.repeat(64))
      ||physical&&(value.command_catalog_sha256!==PHYSICAL_CATALOG||value.surface_protocol_version!==1||value.surface_capabilities!=='8225'
        ||value.mouse_input_version!==1||value.key_mapping_version!==1||value.display_scale!==1))
    throw new BridgeError('Unsupported retained document engine profile/identity');
  return Object.freeze({...value});
}
const EDITOR_PINS=Object.freeze({
  contract_sha256:'0d43707e404979a38e0e8d7a7bc47042be95ae54216ed118a4de3314302b8c9c',
  base_header_sha256:DOCUMENT_PINS.base_header_sha256,document_header_sha256:DOCUMENT_PINS.extension_header_sha256,
  document_contract_sha256:DOCUMENT_PINS.contract_sha256,document_catalog_sha256:DOCUMENT_PINS.document_catalog_sha256,
  physical_catalog_sha256:PHYSICAL_CATALOG,editor_header_sha256:'bdd9bf16765513be402481ab85dd596263fd4ac66a0dfc1dcc7ba5314ec85034',
  editor_catalog_sha256:'34fadacf563a00918255e4dc94b196bf0dc5c8ed57c7165e3da1e5fdd4d06bb8',
  editor_schema_sha256:'f2a6202056bd7fb6872539ba1e8806296ae6f6409ab2a21b9b581f19a4c7d4b1',
  document_schema_sha256:DOCUMENT_PINS.document_schema_sha256,action_ack_schema_sha256:DOCUMENT_PINS.action_ack_schema_sha256});
// Explicit editor2035 is a separate retained generation. Its complete facts
// never enter either frozen document validator or the legacy empty catalog.
export function validateEditorEngineProfile(value){
  const expected={schema_version:1,kind:'foundation-copied-engine-editor-v1',target:'browser-wasm32',
    binding:'copied-owner-bridge/direct-worker-editor-v1',pointer_bits:32,pthread:false,shared_memory:false,
    bridge_abi:BRIDGE_VERSION,capabilities:'2035',provider_abi_major:1,provider_abi_minor:1,host_abi_major:1,host_abi_minor:0,
    editor_profile:'foundation-engine-copied2035-ndv2-editor-v1',...EDITOR_PINS,viewport_width:800,viewport_height:600,
    surface_protocol_version:2,surface_capabilities:'8255',mouse_input_version:1,key_mapping_version:1,editor_protocol_version:1,display_scale:1,
    editor_query_max_bytes:236,editor_reply_capacity:MAX_SERVICE,editor_command_max_bytes:MAX_SERVICE};
  if(!value||Object.getPrototypeOf(value)!==Object.prototype)throw new BridgeError('Unsupported retained editor engine profile/identity');
  const fields=[...Object.keys(expected),'build_sha256','source_recipe_sha256'],descriptors=Object.getOwnPropertyDescriptors(value);
  if(Reflect.ownKeys(descriptors).length!==fields.length||fields.some(key=>!Object.hasOwn(descriptors,key)||!Object.hasOwn(descriptors[key],'value')||!descriptors[key].enumerable))
    throw new BridgeError('Unsupported retained editor engine facts shape');
  const actual={};for(const key of fields)Object.defineProperty(actual,key,{value:descriptors[key].value,enumerable:true});
  if(Object.keys(expected).some(key=>actual[key]!==expected[key])
      ||!['build_sha256','source_recipe_sha256'].every(key=>hash(actual[key])&&actual[key]!=='0'.repeat(64)))
    throw new BridgeError('Unsupported retained editor engine profile/identity');
  return Object.freeze(actual);
}

// Editor facts use one strict owned flat JSON parser at every copied boundary.
// Escaped keys are compared after decoding; JSON overflow and unpaired UTF-16
// escapes must not turn into silently normalized compiled identity facts.
export function decodeEditorEngineFacts(input){
  const bytes=copyBytes(input,4095),text=decoder.decode(bytes),result={},seen=new Set();
  if(bytes.some(value=>value===0)||text.includes('\uFEFF'))throw new BridgeError('Invalid editor facts UTF-8/BOM/NUL');
  const string=/"(?:[^"\\\u0000-\u001f]|\\(?:["\\/bfnrt]|u[0-9a-fA-F]{4}))*"/y,
    scalar=/(?:true|false|null|-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?)/y;
  let offset=0;
  const space=()=>{while(offset<text.length&&/[ \t\r\n]/.test(text[offset]))++offset;};
  const token=expression=>{
    expression.lastIndex=offset;const found=expression.exec(text);
    if(!found)throw new BridgeError('Invalid editor facts flat JSON');
    offset=expression.lastIndex;const value=JSON.parse(found[0]);
    if(typeof value==='number'&&!Number.isFinite(value))throw new BridgeError('Nonfinite editor facts');
    if(typeof value==='string')for(let i=0;i<value.length;++i){
      const unit=value.charCodeAt(i);
      if(unit===0||unit===0xfeff||unit>=0xdc00&&unit<=0xdfff)throw new BridgeError('Invalid editor facts scalar string');
      if(unit>=0xd800&&unit<=0xdbff){const next=value.charCodeAt(++i);if(!(next>=0xdc00&&next<=0xdfff))throw new BridgeError('Invalid editor facts surrogate');}
    }
    return value;
  };
  space();if(text[offset++]!=='{')throw new BridgeError('Invalid editor facts object');space();
  if(text[offset]!=='}')for(;;){
    const key=token(string);if(seen.has(key))throw new BridgeError('Duplicate decoded editor facts key');seen.add(key);
    space();if(text[offset++]!==':')throw new BridgeError('Invalid editor facts field');space();
    const value=token(text[offset]==='"'?string:scalar);Object.defineProperty(result,key,{value,enumerable:true});space();
    if(text[offset]!==',')break;++offset;space();
  }
  if(text[offset++]!=='}')throw new BridgeError('Invalid editor facts field');space();
  if(offset!==text.length)throw new BridgeError('Trailing editor facts JSON');
  return validateEditorEngineProfile(result);
}

const selectedProfile=value=>value?.kind==='foundation-copied-engine-editor-v1'?validateEditorEngineProfile(value):
  value?.kind==='foundation-copied-engine-document-v2'?validateDocumentEngineProfile(value):
  value?.kind==='foundation-copied-engine-physical-v1'?validatePhysicalEngineProfile(value):validateEngineProfile(value);
const editorProfile=value=>value?.kind==='foundation-copied-engine-editor-v1';
const documentProfile=value=>value?.kind==='foundation-copied-engine-document-v2'||editorProfile(value);
const physicalProfile=value=>value?.kind==='foundation-copied-engine-physical-v1'||documentProfile(value)&&['2003','2035'].includes(value.capabilities);

// This read-only query precedes even construction of the engine factory. The
// returned JSON is copied from the current memory before free or another call.
export function inspectKernelPhysicalProfile(module,profile,check=()=>{}){
  const expected=validatePhysicalEngineProfile(profile),capacity=4096;
  if(typeof module?._gui_web_engine_input_describe_v1!=='function'||typeof module._malloc!=='function'||typeof module._free!=='function')
    throw new BridgeError('Retained kernel lacks physical input facts; explicit maintenance required');
  let pointer=0,poisoned=false;
  const live=()=>{try{check();}catch(error){poisoned=true;throw new BridgeError(String(error.message||error),{terminal:true});}};
  const memory=()=>{
    let buffer;try{const value=module.HEAPU8;if(getTag.call(value)!=='Uint8Array')throw Error();buffer=getBuffer.call(value);
      if(!(buffer instanceof BufferType))throw Error();}catch{poisoned=true;throw new BridgeError('Missing private kernel memory',{terminal:true});}
    if(!integer(pointer)||pointer===0||pointer>buffer.byteLength||capacity>buffer.byteLength-pointer){poisoned=true;throw new BridgeError('Invalid physical facts output span',{terminal:true});}
    return new ByteArray(buffer,pointer,capacity);
  };
  try{
    try{pointer=module._malloc(capacity);}catch(error){poisoned=true;throw new BridgeError(String(error.message||error),{terminal:true});}
    live();
    if(pointer===0)throw new BridgeError('Physical facts allocation refused',{code:CONTROL.LIMIT});
    memory();let written;
    try{written=module._gui_web_engine_input_describe_v1(pointer,capacity);}catch(error){poisoned=true;throw new BridgeError(String(error.message||error),{terminal:true});}
    live();
    if(!integer(written,capacity-1)||written===0)throw new BridgeError('Retained kernel does not provide physical input facts; explicit maintenance required');
    const bytes=copyBytes(memory().subarray(0,written),capacity);
    if(bytes.some(value=>value===0))throw new BridgeError('Physical input facts contain a NUL');
    const actual=validatePhysicalEngineProfile(decodeJSON(bytes));
    if(Object.keys(expected).some(key=>actual[key]!==expected[key]))throw new BridgeError('Compiled kernel physical input facts differ from retained profile');
    return actual;
  }catch(error){
    if(error instanceof BridgeError)throw error;
    throw new BridgeError(String(error.message||error));
  }finally{
    if(pointer&&!poisoned)try{module._free(pointer);live();}catch(error){poisoned=true;throw new BridgeError(String(error.message||error),{terminal:true});}
  }
}

// Separate read-only export: no absent/disabled/legacy getter can infer an
// upgrade. Reacquire memory after allocation and after the export may grow it.
export function inspectKernelDocumentProfile(module,profile,check=()=>{}){
  const expected=validateDocumentEngineProfile(profile),capacity=4096;
  if(typeof module?._gui_web_engine_document_describe_v1!=='function'||typeof module._malloc!=='function'||typeof module._free!=='function')
    throw new BridgeError('Retained kernel lacks document facts; explicit maintenance required');
  let pointer=0,poisoned=false;
  const live=()=>{try{check();}catch(error){poisoned=true;throw new BridgeError(String(error.message||error),{terminal:true});}};
  const memory=()=>{
    let buffer;try{const value=module.HEAPU8;if(getTag.call(value)!=='Uint8Array')throw Error();buffer=getBuffer.call(value);
      if(!(buffer instanceof BufferType))throw Error();}catch{poisoned=true;throw new BridgeError('Missing private kernel memory',{terminal:true});}
    if(!integer(pointer)||pointer===0||pointer>buffer.byteLength||capacity>buffer.byteLength-pointer){poisoned=true;throw new BridgeError('Invalid document facts output span',{terminal:true});}
    return new ByteArray(buffer,pointer,capacity);
  };
  try{
    try{pointer=module._malloc(capacity);}catch(error){poisoned=true;throw new BridgeError(String(error.message||error),{terminal:true});}
    live();
    if(pointer===0)throw new BridgeError('Document facts allocation refused',{code:CONTROL.LIMIT});
    memory();let written;
    try{written=module._gui_web_engine_document_describe_v1(pointer,capacity);}catch(error){poisoned=true;throw new BridgeError(String(error.message||error),{terminal:true});}
    live();
    if(!integer(written,capacity-1)||written===0)throw new BridgeError('Retained kernel does not provide document facts; explicit maintenance required');
    const bytes=copyBytes(memory().subarray(0,written),capacity);
    if(bytes.some(value=>value===0))throw new BridgeError('Document facts contain a NUL');
    const actual=validateDocumentEngineProfile(decodeJSON(bytes));
    if(Object.keys(expected).some(key=>actual[key]!==expected[key]))throw new BridgeError('Compiled kernel document facts differ from retained profile');
    return actual;
  }catch(error){
    if(error instanceof BridgeError)throw error;
    throw new BridgeError(String(error.message||error));
  }finally{
    if(pointer&&!poisoned)try{module._free(pointer);live();}catch(error){poisoned=true;throw new BridgeError(String(error.message||error),{terminal:true});}
  }
}

// The editor getter is a distinct pre-factory capability query. Any trap,
// malformed output or failed ownership check ends this scratch allocation's
// authority; no cleanup export follows uncertain native execution.
export function inspectKernelEditorProfile(module,profile,check=()=>{}){
  const expected=validateEditorEngineProfile(profile),capacity=4096;
  const exports={};
  for(const name of ['_gui_web_engine_editor_describe_v1','_malloc','_free']){
    exports[name]=module?.[name];check();
    if(typeof exports[name]!=='function')throw new BridgeError('Retained kernel lacks editor facts; explicit maintenance required');
  }
  const live=()=>{check();};
  const invoke=(name,args)=>{live();const result=Reflect.apply(exports[name],module,args);live();return result;};
  try{
    const pointer=invoke('_malloc',[capacity]);
    if(pointer===0)throw new BridgeError('Editor facts allocation refused',{code:CONTROL.LIMIT});
    const memory=()=>{
      const heap=module.HEAPU8;live();
      let buffer;try{if(getTag.call(heap)!=='Uint8Array')throw Error();buffer=getBuffer.call(heap);if(!(buffer instanceof BufferType))throw Error();}
      catch{throw new BridgeError('Missing private kernel editor facts memory',{terminal:true});}
      if(getOffset.call(heap)!==0||getLength.call(heap)!==buffer.byteLength||!integer(pointer)||pointer>buffer.byteLength||capacity>buffer.byteLength-pointer)
        throw new BridgeError('Invalid editor facts output span',{terminal:true});
      return new ByteArray(buffer,pointer,capacity);
    };
    memory();const written=invoke('_gui_web_engine_editor_describe_v1',[pointer,capacity]);
    if(!integer(written,capacity-1)||written===0)throw new BridgeError('Retained kernel does not provide editor facts; explicit maintenance required');
    const actual=decodeEditorEngineFacts(copyBytes(memory().subarray(0,written),capacity));live();
    if(Object.keys(expected).some(key=>actual[key]!==expected[key]))throw new BridgeError('Compiled kernel editor facts differ from retained profile');
    invoke('_free',[pointer]);return actual;
  }catch(error){throw new BridgeError(String(error.message||error),{terminal:true,code:error.code??null});}
}

const PHYSICAL_COMMANDS=Object.freeze({
  1:{maximum:160,minimum:33,schema:'86b7baad1c95bfb8de3e6b7a9a7c433b528278bbcf84199ca0b2b4ee6134dbc9'},
  3:{maximum:32,minimum:32,schema:'eef60cda2aa7b791641b0e5082d551ec37c10b8d92ca4cc71f13be0af45321d9'},
  5:{maximum:80,minimum:80,schema:'6a15d0e2f814564ce263824dd782335bb327b886e982aefec32476a29b0fd4a3'}});
const commandSequence=bytes=>{
  if(bytes.byteLength<56||bytes.byteLength>216)throw new BridgeError('Malformed physical command size',{terminal:true});
  const view=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength),operation=view.getUint32(0,true),descriptor=PHYSICAL_COMMANDS[operation],length=view.getUint32(52,true);
  if(!descriptor||view.getUint32(4,true)||!view.getBigUint64(8,true)||view.getUint32(48,true)!==16
      ||length!==bytes.byteLength-56||length<descriptor.minimum||length>descriptor.maximum
      ||Array.from(bytes.subarray(16,48),value=>value.toString(16).padStart(2,'0')).join('')!==descriptor.schema)
    throw new BridgeError('Malformed physical command/catalog authority',{terminal:true});
  return view.getBigUint64(8,true);
};
const commandResult=(reply,sequence)=>{
  if(reply.control!==CONTROL.OK||reply.service!==0||reply.source!==0||reply.payload.byteLength!==24)
    throw new BridgeError('Malformed physical command receipt',{terminal:true});
  const view=new DataView(reply.payload.buffer,reply.payload.byteOffset,reply.payload.byteLength),status=view.getInt32(0,true),disposition=view.getUint32(4,true),handled=view.getUint32(20,true);
  if(view.getBigUint64(8,true)!==sequence||view.getUint32(16,true)!==0||handled>1
      ||!(status===0&&disposition===1||status>=-8&&status<=-1&&[0,2].includes(disposition)&&handled===0))
    throw new BridgeError('Invalid physical command disposition/sequence',{terminal:true});
  return {status,disposition};
};

const digestHex=bytes=>Array.from(bytes,value=>value.toString(16).padStart(2,'0')).join('');
const sameTarget=(a,b)=>['worker','instance','document','generation'].every(key=>a[key]===b[key]);
const documentPacketJoin=(bytes,kind,work)=>{
  if(bytes.byteLength<48)return false;
  const view=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);
  return bytes[0]===78&&bytes[1]===68&&bytes[2]===86&&bytes[3]===50&&view.getUint16(4,true)===2&&view.getUint16(6,true)===kind
    &&view.getBigUint64(8,true)===work.identity.instance&&view.getBigUint64(16,true)===work.identity.generation
    &&view.getBigUint64(24,true)===work.identity.document&&view.getBigUint64(32,true)===work.sequence;
};
const documentWork=reply=>{
  const body=reply.payload;
  if(reply.service!==0||reply.source!==0||!reply.transfer||!reply.identity.instance||!reply.identity.document||!reply.identity.generation
      ||body.byteLength<DOCUMENT_WORK_PREFIX||body.byteLength>DOCUMENT_WORK_PREFIX+6246)
    throw new BridgeError('Malformed document work authority/size',{terminal:true});
  const view=new DataView(body.buffer,body.byteOffset,body.byteLength),kind=view.getUint32(0,true),operation=view.getUint32(4,true),sequence=view.getBigUint64(8,true),
    capacity=view.getUint32(48,true),length=view.getUint32(52,true),schema=digestHex(body.subarray(16,48)),payload=copyBytes(body.subarray(DOCUMENT_WORK_PREFIX),6246);
  if(!sequence||length!==payload.byteLength)throw new BridgeError('Malformed document work length/sequence',{terminal:true});
  const work={kind,operation,sequence,capacity,schema,payload,identity:reply.identity,transfer:reply.transfer};
  if(kind===1||kind===2){
    if(sequence===U64_MAX||operation!==(kind===1?3:6)||capacity!==MAX_SERVICE||schema!==DOCUMENT_PINS.document_schema_sha256
        ||kind===1&&length!==48||kind===2&&(length<81||length>6246)||!documentPacketJoin(payload,kind,work))
      throw new BridgeError('Malformed document query/form catalog or native join',{terminal:true});
    const nonce=new DataView(payload.buffer).getBigUint64(40,true);
    if(kind===1?nonce===0n:nonce!==0n)throw new BridgeError('Malformed document query/form token',{terminal:true});
    work.copiedCapacity=RECEIPT_BYTES+(kind===1?16:24)+capacity;
  }else if(kind===3){
    if(operation!==7||capacity!==16||schema!==DOCUMENT_PINS.action_ack_schema_sha256||length!==8)
      throw new BridgeError('Malformed document action ACK catalog',{terminal:true});
    const original=new DataView(payload.buffer).getBigUint64(0,true);
    if(!original||original===U64_MAX||sequence<=original)throw new BridgeError('Malformed document action ACK sequence',{terminal:true});
    work.original=original;work.copiedCapacity=RECEIPT_BYTES+24+16;
  }else throw new BridgeError('Unknown document work kind',{terminal:true});
  return work;
};
const documentEngineInput=work=>{
  const query=work.kind===1,prefix=query?48:56,bytes=new ByteArray(prefix+work.payload.byteLength),view=new DataView(bytes.buffer);
  view.setUint32(0,work.operation,true);
  if(!query)view.setBigUint64(8,work.sequence,true);
  for(let i=0;i<32;i++)bytes[(query?8:16)+i]=parseInt(work.schema.slice(2*i,2*i+2),16);
  view.setUint32(query?40:48,work.capacity,true);view.setUint32(query?44:52,work.payload.byteLength,true);set(bytes,work.payload,prefix);
  return bytes;
};
const validFormCompletionPrefix=(bytes,handled)=>{
  if(bytes.byteLength<52)return false;
  const outcome=bytes[48],code=bytes[49],flags=bytes[50],readback=bytes[51];
  // Mirror the provider's closed completion prefix before any cleanup export.
  // Deep paired-publication validation remains the native codec's obligation.
  return outcome<=2&&code<=8&&!(flags&~3)&&readback<=1&&!(outcome===1&&(flags&1))
    &&(!(flags&2)||!!(flags&1))&&(outcome!==0||!!readback&&code===0)
    &&(!!readback||bytes.byteLength===52)&&handled===(flags&1);
};
const documentResult=(reply,work)=>{
  if(reply.control!==CONTROL.OK||reply.service!==0||reply.source!==0||reply.transfer!==work.transfer||!sameTarget(reply.identity,work.identity))
    throw new BridgeError('Document result changed its original authority/status',{terminal:true});
  const query=work.kind===1,prefix=query?16:24,body=reply.payload;
  if(body.byteLength<prefix)throw new BridgeError('Truncated document result metadata',{terminal:true});
  const view=new DataView(body.buffer,body.byteOffset,body.byteLength),status=view.getInt32(0,true),disposition=query?0:view.getUint32(4,true),
    written=view.getUint32(query?4:16,true),handled=query?0:view.getUint32(20,true),revision=query?view.getBigUint64(8,true):0n,
    bytes=copyBytes(body.subarray(prefix),work.capacity);
  if(status>0||status<-8||written!==bytes.byteLength||written>work.capacity||handled>1||disposition>2
      ||!query&&view.getBigUint64(8,true)!==work.sequence)
    throw new BridgeError('Malformed document result count/sequence/status',{terminal:true});
  let unknown=status===-8||disposition===2;
  if(query){
    if(status!==0?(written!==0||revision!==0n):(!revision||!documentPacketJoin(bytes,4,work)
        ||new DataView(bytes.buffer).getBigUint64(40,true)!==new DataView(work.payload.buffer).getBigUint64(40,true)))
      throw new BridgeError('Malformed document query result/native join',{terminal:true});
  }else{
    if(disposition===1&&status!==0||disposition===0&&(status===0||handled!==0||written!==0))
      throw new BridgeError('Invalid document command disposition',{terminal:true});
    // A naturally returned disposition2 is bounded forensic evidence only.
    // Preserve raw bytes/handled exactly; it proves no NDV2 result or ACK.
    if(disposition===1){
      if(work.kind===2){
        if(!validFormCompletionPrefix(bytes,handled)||!documentPacketJoin(bytes,5,work)||new DataView(bytes.buffer).getBigUint64(40,true)!==0n)
          throw new BridgeError('Malformed document form result/native join',{terminal:true});
        // A checked inner form unknown is terminal even when transport consumed
        // it successfully. Detect it before the endpoint's cleanup exports.
        unknown=unknown||bytes[48]===2;
      }else{
        const ack=bytes.byteLength===16?new DataView(bytes.buffer):null;
        if(!ack||handled||ack.getBigUint64(0,true)!==work.original||ack.getUint32(8,true)>2||ack.getUint32(12,true))
          throw new BridgeError('Malformed document action ACK result',{terminal:true});
      }
    }
  }
  return {status,disposition,written,handled,revision,bytes,unknown};
};
const documentResultBody=(work,result)=>{
  const bytes=new ByteArray(DOCUMENT_RESULT_PREFIX+result.bytes.byteLength),view=new DataView(bytes.buffer);
  view.setUint32(0,work.kind,true);view.setBigUint64(8,work.sequence,true);view.setInt32(16,result.status,true);
  view.setUint32(20,result.disposition,true);view.setUint32(24,result.written,true);view.setUint32(28,result.handled,true);
  view.setBigUint64(32,result.revision,true);set(bytes,result.bytes,DOCUMENT_RESULT_PREFIX);return bytes;
};

// This new catalog alone carries a one-MiB binary command plus its prefix.
// Legacy service, physical and document bounds remain their original values.
const editorPacketJoin=(bytes,kind,work)=>{
  const offset=kind===2?24:16;
  if(bytes.byteLength<offset+40||bytes.byteLength>MAX_SERVICE)return false;
  const view=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);
  return [66,73,66,69,68,86,49,0].every((value,index)=>bytes[index]===value)
    &&view.getUint16(8,true)===kind&&view.getUint16(10,true)===0&&view.getUint32(12,true)===bytes.byteLength
    &&['worker','instance','document','generation'].every((key,index)=>view.getBigUint64(offset+8*index,true)===work.identity[key])
    &&view.getBigUint64(offset+32,true)===work.sequence;
};
const editorCommandPrefix=(input,identity)=>{
  let bytes;try{bytes=copyBytes(input,MAX_SERVICE+56);}catch{return false;}
  if(bytes.byteLength<112)return false;
  const view=new DataView(bytes.buffer),operation=view.getUint32(0,true),sequence=view.getBigUint64(8,true);
  return [8,9].includes(operation)&&!view.getUint32(4,true)&&sequence>0n&&sequence<U64_MAX
    &&digestHex(bytes.subarray(16,48))===EDITOR_PINS.editor_schema_sha256&&view.getUint32(48,true)===MAX_SERVICE
    &&view.getUint32(52,true)===bytes.byteLength-56
    &&editorPacketJoin(bytes.subarray(56),operation===8?3:5,{identity,sequence});
};
const editorCommandRecord=input=>{
  try{const record=decodeRecord(input,{receipt:false,maximum:HEADER_BYTES+56+MAX_SERVICE});
    return record.kind===ENGINE.COMMAND&&record.source===0&&editorCommandPrefix(record.payload,record.identity);
  }catch{return false;}
};
const editorWork=reply=>{
  const body=reply.payload;
  if(reply.service!==0||reply.source!==0||!reply.transfer||!reply.identity.instance||!reply.identity.document||!reply.identity.generation
      ||body.byteLength<EDITOR_WORK_PREFIX+56||body.byteLength>EDITOR_WORK_PREFIX+MAX_SERVICE)
    throw new BridgeError('Malformed editor work authority/size',{terminal:true});
  const view=new DataView(body.buffer,body.byteOffset,body.byteLength),kind=view.getUint32(0,true),operation=view.getUint32(4,true),
    sequence=view.getBigUint64(8,true),capacity=view.getUint32(48,true),length=view.getUint32(52,true),schema=digestHex(body.subarray(16,48));
  const work={kind,operation,sequence,capacity,schema,payload:copyBytes(body.subarray(EDITOR_WORK_PREFIX),MAX_SERVICE),identity:reply.identity,transfer:reply.transfer};
  if(!sequence||sequence===U64_MAX||![1,2,3].includes(kind)||operation!==(kind===1?4:kind===2?8:9)
      ||capacity!==MAX_SERVICE||schema!==EDITOR_PINS.editor_schema_sha256||length!==work.payload.byteLength
      ||kind===1&&length>236||!editorPacketJoin(work.payload,kind===1?1:kind===2?3:5,work))
    throw new BridgeError('Malformed editor catalog, sequence or five-field native join',{terminal:true});
  work.copiedCapacity=RECEIPT_BYTES+(kind===1?16:24)+capacity;return work;
};
const editorResult=(reply,work)=>{
  if(reply.control!==CONTROL.OK||reply.service!==0||reply.source!==0||reply.transfer!==work.transfer||!sameTarget(reply.identity,work.identity))
    throw new BridgeError('Editor result changed its original authority/status',{terminal:true});
  const query=work.kind===1,prefix=query?16:24,body=reply.payload;
  if(body.byteLength<prefix)throw new BridgeError('Truncated editor result metadata',{terminal:true});
  const view=new DataView(body.buffer,body.byteOffset,body.byteLength),status=view.getInt32(0,true),disposition=query?0:view.getUint32(4,true),
    written=view.getUint32(query?4:16,true),handled=query?0:view.getUint32(20,true),revision=query?view.getBigUint64(8,true):0n,
    bytes=copyBytes(body.subarray(prefix),work.capacity);
  if(status>0||status<-8||written!==bytes.byteLength||handled>1||disposition>2||!query&&view.getBigUint64(8,true)!==work.sequence)
    throw new BridgeError('Malformed editor result count, status or sequence',{terminal:true});
  let unknown=status===-8||disposition===2;
  if(query){
    if(status===0){
      if(!revision||!editorPacketJoin(bytes,2,work)||new DataView(bytes.buffer).getBigUint64(16,true)!==revision)
        throw new BridgeError('Malformed editor projection result/native join',{terminal:true});
    }else if(status!==-8&&(written||revision))throw new BridgeError('Noncanonical rejected editor projection',{terminal:true});
  }else if(disposition===0){
    if(status===0||written||handled)throw new BridgeError('Noncanonical rejected editor command',{terminal:true});
  }else if(disposition===1){
    if(status!==0||bytes.byteLength<60||!editorPacketJoin(bytes,4,work))throw new BridgeError('Malformed editor command result/native join',{terminal:true});
    const outcome=new DataView(bytes.buffer).getUint32(56,true);
    if(outcome>3)throw new BridgeError('Unknown editor semantic outcome',{terminal:true});
    unknown=outcome===3;
  }
  return {status,disposition,written,handled,revision,bytes,unknown};
};

const replayFields=(value,fields)=>{
  if(!value||Object.getPrototypeOf(value)!==Object.prototype)throw new BridgeError('Invalid document replay selector');
  const descriptors=Object.getOwnPropertyDescriptors(value);
  if(Reflect.ownKeys(descriptors).length!==fields.length||fields.some(key=>!Object.hasOwn(descriptors,key)
      ||!Object.hasOwn(descriptors[key],'value')||!descriptors[key].enumerable))throw new BridgeError('Invalid document replay selector');
  const result={};for(const key of fields)result[key]=descriptors[key].value;return result;
};
const replaySelector=value=>{
  const selected=replayFields(value,['kind','identity','transfer','sequence']);
  selected.identity=replayFields(selected.identity,['worker','instance','document','generation']);
  if(![2,3].includes(selected.kind)||!u64(selected.transfer)||!selected.transfer||!u64(selected.sequence)||!selected.sequence
      ||selected.kind===2&&selected.sequence===U64_MAX
      ||Object.values(selected.identity).some(value=>!u64(value)||!value))throw new BridgeError('Invalid document replay selector');
  return selected;
};
const exactBytes=(a,b)=>a.byteLength===b.byteLength&&a.every((value,index)=>value===b[index]);
const knownFormCompletion=result=>{
  const bytes=result.bytes;
  return !result.status&&result.disposition===1&&!result.unknown&&validFormCompletionPrefix(bytes,result.handled)
    &&bytes[48]<=1;
};

export function createEngineKernelBridge({kernel,engine,workerEpoch,post=task=>setTimeout(task,0),timer=globalThis,startTimeout=30000,
  abandonClosedDocumentOutcomes=false,onTerminalOutcome=null,onFailure=()=>{},onDirty=()=>{}}){
  if(kernel.role!=='kernel'||engine.role!=='engine'||kernel.memory===engine.memory||!u64(workerEpoch)||workerEpoch===0n)throw new BridgeError('Bridge needs distinct private instances and a fresh Worker epoch');
  if(typeof abandonClosedDocumentOutcomes!=='boolean'||onTerminalOutcome!==null&&typeof onTerminalOutcome!=='function')throw new BridgeError('Invalid immutable closed-document policy');
  let identity={worker:workerEpoch,instance:0n,document:0n,generation:0n},state='new',active=false,depth=0,pumping=false,
    scheduled=false,delivery=null,ack=null,command=null,documentCall=null,documentEnabled=false,documentIdle=false,editorEnabled=false,physicalInput=false,lastCommandSequence=0n,terminalOutcome=null,retirement=null,engineTimer=null,currentTransfer=0n,persistence=null,inspected=null,advanceRequested=false,inspecting=false,startTimer=null,lastReady=null,metadataIdentity=identity;
  const retired=new Set(),identityKey=value=>[value.instance,value.document,value.generation].join('/'),sameIdentity=(a,b)=>['worker','instance','document','generation'].every(k=>a[k]===b[k]);
  let readyResolve,readyReject;const ready=new Promise((resolve,reject)=>{readyResolve=resolve;readyReject=reject;});ready.catch(()=>{});
  let closedResolve;const closed=new Promise(resolve=>{closedResolve=resolve;});
  // These are the provider's bounded retained form/latest-ACK/code-zero proof
  // slots, never a queue of new native work. Buffers stay private and owned.
  let formReplay=null,latestAckReplay=null,retirementAckReplay=null,replayPending=null,replayActive=false;
  const clearDocumentReplays=error=>{
    formReplay=null;latestAckReplay=null;retirementAckReplay=null;
    const pending=replayPending;replayPending=null;if(pending)pending.reject(error);
  };
  const replayRetained=record=>record===formReplay||record===latestAckReplay||record===retirementAckReplay;
  const evictDocumentReplays=target=>{
    if(formReplay&&sameIdentity(formReplay.work.identity,target))formReplay=null;
    if(latestAckReplay&&sameIdentity(latestAckReplay.work.identity,target))latestAckReplay=null;
    if(retirementAckReplay&&sameIdentity(retirementAckReplay.work.identity,target))retirementAckReplay=null;
  };
  const clearTimers=()=>{if(engineTimer!==null)timer.clearTimeout(engineTimer);if(startTimer!==null)timer.clearTimeout(startTimer);engineTimer=null;startTimer=null;};
  const fail=error=>{if(state==='failed'||state==='closed')return;state='failed';clearDocumentReplays(error);clearTimers();readyReject(error);closedResolve({graceful:false});onFailure(error instanceof Error?error:Error(String(error)));};
  const terminal=error=>{fail(error);throw new BridgeError(String(error.message||error),{terminal:true});};
  const queued=action=>post(()=>{if(state==='ready'||state==='closing'){try{action();}catch(error){fail(error);}}});
  const requireOK=reply=>{if(reply.control!==CONTROL.OK)throw new BridgeError('Kernel/engine operation refused',{code:reply.control});return reply;};
  const kernelCall=(op,payload=new ByteArray(),options={},target=identity)=>{
    const capacity=op===OP.PEEK_EDITOR_WORK?RECEIPT_BYTES+EDITOR_WORK_PREFIX+MAX_SERVICE:MAX_SERVICE+RECEIPT_BYTES;
    const bytes=kernel.call(op,encodeRecord(op,target,payload,options),capacity);
    return decodeRecord(bytes,{kind:op,worker:workerEpoch,maximum:capacity});
  };
  const engineCall=(op,payload=new ByteArray(),transfer=0n,target=identity,validate=()=>{},options={})=>{
    if(active||pumping||state==='closed'||state==='failed')throw new BridgeError('Engine entry refused by owner turn/barrier');
    active=true;currentTransfer=transfer;
    try{
      const raw=engine.call(op,encodeRecord(op,target,payload,{transfer,editorProfile:editorEnabled?inspected:null}),options.capacity??(op===ENGINE.COMMAND?104:MAX_SERVICE+RECEIPT_BYTES),reply=>{
        if(depth!==0||state==='failed')throw new BridgeError('Engine returned with an incomplete/failed native callback guard',{terminal:true});
        if(reply.service!==0)throw new BridgeError('Engine used the kernel service-status field',{terminal:true});
        if([ENGINE.DELIVER_SERVICES,ENGINE.COLLECT_ACK].includes(op)){
          if(reply.control!==CONTROL.OK||reply.payload.byteLength!==4||![RESULT.ACCEPTED,RESULT.REJECTED].includes(new DataView(reply.payload.buffer).getUint32(0,true)))
            throw new BridgeError('Malformed effect delivery disposition',{terminal:true});
          if(reply.transfer!==transfer||['instance','document','generation'].some(key=>reply.identity[key]!==target[key]))
            throw new BridgeError('Effect reply changed its document/transfer identity',{terminal:true});
        }
        if(op===ENGINE.DISPOSE_RETIRED&&(reply.control!==CONTROL.OK||reply.payload.byteLength!==4
            ||new DataView(reply.payload.buffer).getInt32(0,true)!==0||reply.transfer!==transfer||!sameIdentity(reply.identity,target)))
          throw new BridgeError('Retired engine disposal failed or changed its authority',{terminal:true});
        return validate(reply);
      },options.beforeEntry,()=>{if(state==='failed')throw new BridgeError('Host failure forbids further interpreter exports',{terminal:true});});
      const reply=decodeRecord(raw,{kind:op,worker:workerEpoch,maximum:options.capacity??MAX_SERVICE+RECEIPT_BYTES});
      if(depth!==0)return terminal(Error('Engine returned with an incomplete native callback guard'));
      if(state==='failed')return terminal(Error('Engine caught a terminal host failure'));
      if(op===ENGINE.DISPOSE_RETIRED)evictDocumentReplays(target);
      return reply;
    }catch(error){return terminal(error);}
    finally{active=false;currentTransfer=0n;}
  };
  const request=()=>{
    if(scheduled||!['ready','closing'].includes(state))return;scheduled=true;
    queued(()=>{scheduled=false;drive();});
  };
  const outcome=(op,transfer,result,target)=>requireOK(kernelCall(op,scalar32(result),{transfer},target));
  const deliver=()=>{
    if(!delivery||delivery.blocked)return;
    if(retired.has(identityKey(delivery.identity))){request();return;}
    const reply=engineCall(ENGINE.DELIVER_SERVICES,delivery.payload,delivery.transfer,delivery.identity);
    if(reply.control!==CONTROL.OK||reply.payload.byteLength!==4)return terminal(Error('Malformed engine service delivery result'));
    const disposition=new DataView(reply.payload.buffer).getUint32(0,true);
    if(![RESULT.ACCEPTED,RESULT.REJECTED].includes(disposition))return terminal(Error('Unknown engine delivery disposition'));
    outcome(OP.DELIVERY_RESULT,delivery.transfer,disposition,delivery.identity);
    if(disposition===RESULT.REJECTED){delivery.blocked=true;if(retired.has(identityKey(delivery.identity)))request();return;}
    delivery=null;request();onDirty();
  };
  const collectAck=()=>{
    if(!ack||ack.blocked)return;
    if(retired.has(identityKey(ack.identity))){request();return;}
    const reply=engineCall(ENGINE.COLLECT_ACK,ack.payload,ack.transfer,ack.identity);
    if(reply.control!==CONTROL.OK||reply.payload.byteLength!==4)return terminal(Error('Malformed engine ACK receipt result'));
    const disposition=new DataView(reply.payload.buffer).getUint32(0,true);
    if(![RESULT.ACCEPTED,RESULT.REJECTED].includes(disposition))return terminal(Error('Unknown engine ACK receipt disposition'));
    outcome(OP.ACK_RECEIPT_RESULT,ack.transfer,disposition,ack.identity);
    if(disposition===RESULT.REJECTED){ack.blocked=true;if(retired.has(identityKey(ack.identity)))request();return;}
    ack=null;request();onDirty();
  };
  const executeCommand=()=>{
    const value=command;
    // One synchronous owner task owns PEEK, native entry and the copied result.
    // A navigation in that entry cannot rewrite its captured target/transfer.
    const reply=engineCall(ENGINE.COMMAND,value.payload,value.transfer,value.identity,result=>{
      if(result.transfer!==value.transfer||!sameIdentity(result.identity,value.identity))
        throw new BridgeError('Physical command changed its document/transfer identity',{terminal:true});
      const disposition=commandResult(result,value.sequence);
      if(disposition.disposition===2||disposition.status===-8)return false;
    });
    const result=commandResult(reply,value.sequence);
    const collected=requireOK(kernelCall(OP.COMMAND_RESULT,reply.payload,{transfer:value.transfer},value.identity));
    if(collected.service!==0||collected.source!==0||collected.transfer!==value.transfer||!sameIdentity(collected.identity,value.identity)||collected.payload.byteLength)
      return terminal(Error('Kernel refused the exact physical command result'));
    command=null;
    if(result.disposition===2||result.status===-8)return terminal(Error('Physical command outcome is uncertain; the engine route is closed'));
    request();onDirty();
  };
  const executeDocument=work=>{
    if(work.sequence<=lastCommandSequence)return terminal(Error('Shared physical/document sequence was reused or wrapped'));
    lastCommandSequence=work.sequence;
    documentCall={work,entered:0,left:0,phase:'allocating'};
    const claim=new ByteArray(DOCUMENT_BEGIN_BYTES),view=new DataView(claim.buffer);
    view.setUint32(0,work.kind,true);view.setBigUint64(8,work.sequence,true);
    const input=documentEngineInput(work);
    try{
      const reply=engineCall(work.kind===1?ENGINE.QUERY:ENGINE.COMMAND,input,work.transfer,work.identity,result=>{
        documentCall.phase='returned';
        const parsed=documentResult(result,work),guard=documentCall;
        if(work.kind===3){
          if(guard.entered||guard.left)throw new BridgeError('Callback-bearing action ACK',{terminal:true});
        }else{
          const preentry=parsed.status<0&&!parsed.unknown&&parsed.disposition===0&&!parsed.written&&!parsed.handled&&!parsed.revision;
          if(!(guard.entered===1&&guard.left===1)&&!(preentry&&guard.entered===0&&guard.left===0))
            throw new BridgeError('Document result lacks its complete matching native turn',{terminal:true});
        }
        // Preserve a naturally returned uncertain outcome without another
        // interpreter export, including free. ACK metadata has no Host turn.
        // Neither raw evidence nor its receipt permits automatic effect replay.
        if(parsed.unknown)return false;
      },{capacity:work.copiedCapacity,beforeEntry:()=>{
        const claimed=requireOK(kernelCall(OP.BEGIN_DOCUMENT_WORK,claim,{transfer:work.transfer},work.identity));
        if(claimed.service!==0||claimed.source!==0||claimed.transfer!==work.transfer||!sameIdentity(claimed.identity,work.identity)||claimed.payload.byteLength)
          throw new BridgeError('Kernel refused exact document work claim',{terminal:true});
        documentCall.phase='provider';
      }});
      const result=documentResult(reply,work),collected=requireOK(kernelCall(OP.DOCUMENT_WORK_RESULT,documentResultBody(work,result),{transfer:work.transfer},work.identity));
      if(collected.service!==0||collected.source!==0||collected.transfer!==work.transfer||!sameIdentity(collected.identity,work.identity)||collected.payload.byteLength)
        return terminal(Error('Kernel refused exact owned document result'));
      retainDocumentReplay(work,input,result);
      if(result.unknown)return terminal(Error('Document native outcome is uncertain; no provider replay is allowed'));
      request();onDirty();
    }finally{documentCall=null;}
  };
  const retainDocumentReplay=(work,input,result)=>{
    if(work.kind!==2&&work.kind!==3||result.status||result.disposition!==1||result.unknown)return;
    if(work.kind===2&&!knownFormCompletion(result)){
      clearDocumentReplays(new BridgeError('Unknown or unchecked form completion cannot be replayed'));return;
    }
    const retainedWork=Object.freeze({kind:work.kind,operation:work.operation,sequence:work.sequence,
      identity:Object.freeze({...work.identity}),transfer:work.transfer,capacity:work.capacity,copiedCapacity:work.copiedCapacity,original:work.original});
    const record=Object.freeze({work:retainedWork,input,result:Object.freeze(result)});
    if(work.kind===2){formReplay=record;return;}
    const code=new DataView(result.bytes.buffer,result.bytes.byteOffset,result.bytes.byteLength).getUint32(8,true);
    if(code<=1&&formReplay&&sameIdentity(formReplay.work.identity,work.identity)&&formReplay.work.sequence===work.original)formReplay=null;
    latestAckReplay=record;if(code===0)retirementAckReplay=record;
  };
  const executeDocumentReplay=()=>{
    const pending=replayPending;replayPending=null;const record=pending.record,work=record.work;
    if(state!=='ready'||!replayRetained(record)){
      pending.reject(new BridgeError('Document replay record expired',{code:CONTROL.STALE}));request();return;
    }
    replayActive=true;
    try{
      let actual;
      engineCall(ENGINE.COMMAND,record.input,work.transfer,work.identity,reply=>{
        actual=documentResult(reply,work);const expected=record.result;
        if(actual.unknown||['status','disposition','written','handled','revision'].some(key=>actual[key]!==expected[key])
            ||!exactBytes(actual.bytes,expected.bytes))throw new BridgeError('Cached document result changed its exact owned outcome',{terminal:true});
      },{capacity:work.copiedCapacity});
      pending.resolve(Object.freeze({kind:work.kind,operation:work.operation,identity:Object.freeze({...work.identity}),
        transfer:work.transfer,sequence:work.sequence,status:actual.status,disposition:actual.disposition,written:actual.written,
        handled:actual.handled,revision:actual.revision,bytes:copyBytes(actual.bytes,work.capacity)}));
      request();
    }catch(error){pending.reject(error);}
    finally{replayActive=false;}
  };
  const executeEditor=work=>{
    if(work.sequence<=lastCommandSequence)return terminal(Error('Shared physical/document/editor sequence was reused or wrapped'));
    lastCommandSequence=work.sequence;documentCall={work,editor:true,entered:0,left:0,phase:'allocating'};
    const claim=new ByteArray(EDITOR_BEGIN_BYTES),view=new DataView(claim.buffer);
    view.setUint32(0,work.kind,true);view.setBigUint64(8,work.sequence,true);
    try{
      const reply=engineCall(work.kind===1?ENGINE.QUERY:ENGINE.COMMAND,documentEngineInput(work),work.transfer,work.identity,result=>{
        documentCall.phase='returned';const parsed=editorResult(result,work),guard=documentCall;
        const preentry=parsed.status<0&&!parsed.unknown&&parsed.disposition===0&&!parsed.written&&!parsed.handled&&!parsed.revision;
        if(!(guard.entered===1&&guard.left===1)&&!(preentry&&guard.entered===0&&guard.left===0))
          throw new BridgeError('Editor result lacks its complete matching native turn',{terminal:true});
        if(parsed.unknown)return false;
      },{capacity:work.copiedCapacity,beforeEntry:()=>{
        const claimed=requireOK(kernelCall(OP.BEGIN_EDITOR_WORK,claim,{transfer:work.transfer},work.identity));
        if(claimed.service!==0||claimed.source!==0||claimed.transfer!==work.transfer||!sameIdentity(claimed.identity,work.identity)||claimed.payload.byteLength)
          throw new BridgeError('Kernel refused exact editor work claim',{terminal:true});
        documentCall.phase='provider';
      }});
      const result=editorResult(reply,work),collected=requireOK(kernelCall(OP.EDITOR_WORK_RESULT,documentResultBody(work,result),{transfer:work.transfer},work.identity));
      if(collected.service!==0||collected.source!==0||collected.transfer!==work.transfer||!sameIdentity(collected.identity,work.identity)||collected.payload.byteLength)
        return terminal(Error('Kernel refused exact owned editor result'));
      if(result.unknown)return terminal(Error('Editor native outcome is uncertain; no provider replay or ACK is allowed'));
      request();onDirty();
    }finally{documentCall=null;}
  };
  const drainEditor=target=>{
    if(!editorEnabled)return false;
    const next=kernelCall(OP.PEEK_EDITOR_WORK,new ByteArray(),{},target);
    if(next.control===CONTROL.EMPTY){
      if(![0,2].includes(next.service)||next.source!==0||next.transfer||next.payload.byteLength||!sameIdentity(next.identity,target))
        return terminal(Error('Malformed editor scheduler idle/barrier facts'));
      documentIdle=documentIdle&&next.service===0;return false;
    }
    requireOK(next);executeEditor(editorWork(next));return true;
  };
  const drainDocument=()=>{
    documentIdle=false;
    if(!documentEnabled||!metadataIdentity.instance)return false;
    // last-ready remains scheduler metadata after service authority expires;
    // it never authorizes a new action or substitutes for the original target.
    const target=identity.generation?identity:lastReady??metadataIdentity;
    const next=kernelCall(OP.PEEK_DOCUMENT_WORK,new ByteArray(),{},target);
    if(next.control===CONTROL.EMPTY){
      if(![0,2].includes(next.service)||next.source!==0||next.transfer||next.payload.byteLength||!sameIdentity(next.identity,target))
        return terminal(Error('Malformed document scheduler idle/barrier facts'));
      documentIdle=next.service===0;return drainEditor(target);
    }
    requireOK(next);executeDocument(documentWork(next));return true;
  };
  const retiredReply=reply=>{
    if(reply.service!==0||!reply.transfer||!reply.identity.instance||!reply.identity.document||!reply.identity.generation
        ||reply.identity.instance!==identity.instance||sameIdentity(reply.identity,metadataIdentity))
      return terminal(Error('Malformed retired document authority'));
  };
  const validateTerminalOutcome=reply=>{
    retiredReply(reply);
    const bytes=reply.payload;
    if(bytes.byteLength>=4&&bytes[0]===70&&bytes[1]===75&&bytes[2]===66&&bytes[3]===49){
      const receipt=decodeRecord(bytes,{kind:OP.PEEK_ACK_RECEIPT,worker:workerEpoch});
      if(receipt.control!==CONTROL.OK||receipt.payload.byteLength!==12||!sameIdentity(receipt.identity,reply.identity)
          ||new DataView(receipt.payload.buffer).getUint32(8,true)!==receipt.service)
        return terminal(Error('Malformed abandoned ACK receipt'));
    }else{
      if(bytes.byteLength<64)return terminal(Error('Truncated terminal completion'));
      const view=new DataView(bytes.buffer);
      if(view.getUint32(0,true)!==bytes.byteLength||view.getUint16(4,true)!==1||view.getUint16(6,true)!==0
          ||view.getUint32(8,true)!==4||view.getUint32(12,true)||view.getBigUint64(16,true)!==reply.identity.generation
          ||view.getBigUint64(24,true)===0n||view.getUint32(44,true)!==bytes.byteLength-64
          ||view.getUint32(48,true)>14||view.getUint32(52,true)||view.getBigUint64(56,true))
        return terminal(Error('Malformed terminal completion'));
    }
  };
  const abandonTerminalOutcome=()=>{
    if(!terminalOutcome||terminalOutcome.blocked)return;
    const value=terminalOutcome;
    // Trusted document CLOSE abandons its JavaScript results. This exact copied
    // outcome is not converted to success or delivered to a disposed page. The
    // optional observer has no persistence/history guarantee.
    if(!value.observed){value.observed=true;if(onTerminalOutcome)onTerminalOutcome(Object.freeze({identity:Object.freeze({...value.identity}),bytes:copyBytes(value.payload)}));}
    const reply=kernelCall(OP.RETIREMENT_AUDIT_RESULT,scalar32(RESULT.ABANDONED),{transfer:value.transfer},value.identity);
    if(reply.control!==CONTROL.OK||reply.service!==0){value.blocked=true;return;}
    terminalOutcome=null;request();onDirty();
  };
  const disposeRetired=()=>{
    if(!retirement)return;
    const value=retirement;
    engineCall(ENGINE.DISPOSE_RETIRED,new ByteArray(),value.transfer,value.identity);
    const reply=requireOK(kernelCall(OP.RETIRED_DOCUMENT_RESULT,scalar32(RESULT.ACCEPTED),{transfer:value.transfer},value.identity));
    if(reply.service!==0)return terminal(Error('Kernel refused a completed retired disposal'));
    retired.delete(identityKey(value.identity));retirement=null;request();onDirty();
  };
  const retirementStep=()=>{
    if(!abandonClosedDocumentOutcomes)return false;
    // Resource setup is prospective and does not replace committed service
    // metadata. Its generation-zero tuple cannot select these owner mailboxes.
    const target=metadataIdentity;if(!target.instance)return false;
    const audit=kernelCall(OP.PEEK_RETIREMENT_AUDIT,new ByteArray(),{},target);
    if(audit.control===CONTROL.OK){
      validateTerminalOutcome(audit);
      if(delivery&&sameIdentity(delivery.identity,audit.identity))delivery=null;
      if(ack&&sameIdentity(ack.identity,audit.identity))ack=null;
      terminalOutcome={payload:audit.payload,identity:audit.identity,transfer:audit.transfer,blocked:false,observed:false};
      queued(abandonTerminalOutcome);return true;
    }
    if(audit.control!==CONTROL.EMPTY)return terminal(Error('Kernel terminal-outcome mailbox refused'));
    if(delivery||ack)return terminal(Error('Retired transaction lost its terminal outcome'));
    const next=kernelCall(OP.PEEK_RETIRED_DOCUMENT,new ByteArray(),{},target);
    if(next.control===CONTROL.OK){retiredReply(next);if(next.payload.byteLength)return terminal(Error('Malformed retired disposal entry'));
      retirement={identity:next.identity,transfer:next.transfer};queued(disposeRetired);return true;}
    if(next.control!==CONTROL.EMPTY)return terminal(Error('Kernel retired-document mailbox refused'));
    return false;
  };
  const drive=()=>{
    if(!['ready','closing'].includes(state)||active||depth||pumping||command||documentCall||replayActive||terminalOutcome||retirement)return;
    if(delivery&&!retired.has(identityKey(delivery.identity))||ack&&!retired.has(identityKey(ack.identity)))return;
    if(replayPending){executeDocumentReplay();return;}
    if(retirementStep())return;
    if(delivery||ack)return;
    if(state==='closing'){
      if(drainDocument())return;
      const reply=requireOK(kernelCall(OP.CLOSE,new ByteArray(),{},metadataIdentity));
      if(reply.service===0){state='closed';clearTimers();persistence=null;closedResolve({graceful:true});}
      // Outstanding engine-owned resource leases require a later real owner
      // release. No busy retry loop or invented resource release is permitted.
      else if(reply.service!==2)return terminal(Error('Kernel cleanup did not reach a known pending close'));
      return;
    }
    const target=identity.generation?identity:lastReady;
    if(!target){
      if(documentEnabled){if(drainDocument())return;if(!documentIdle){onDirty();return;}}
      if(advanceRequested){advanceRequested=false;requireOK(engineCall(ENGINE.ADVANCE));}onDirty();return;
    }
    pumping=true;let pumped;
    try{pumped=kernelCall(OP.PUMP_ONE,new ByteArray(),{},target);}finally{pumping=false;}
    if(pumped.control===CONTROL.STALE&&identity.generation===0n){
      if(documentEnabled){if(drainDocument())return;if(!documentIdle){onDirty();return;}}
      else lastReady=null;
      if(advanceRequested){advanceRequested=false;requireOK(engineCall(ENGINE.ADVANCE));}onDirty();return;
    }
    // A real queued native service can wait for its trusted context-retirement
    // command. This exact physical-only refusal is not a delivery/ACK retry.
    const serviceSuspended=(physicalInput||documentEnabled)&&pumped.control===CONTROL.CONFLICT&&pumped.service===2;
    if(!serviceSuspended)requireOK(pumped);
    if(pumped.service===14)return terminal(Error('Service outcome is uncertain; explicit owner recovery required'));
    const receipt=kernelCall(OP.PEEK_ACK_RECEIPT,new ByteArray(),{},target);
    if(receipt.control===CONTROL.OK){ack={payload:receipt.payload,identity:receipt.identity,transfer:receipt.transfer,blocked:false};queued(collectAck);return;}
    if(receipt.control!==CONTROL.EMPTY)return terminal(Error('ACK mailbox refused'));
    const next=kernelCall(OP.PEEK_DELIVERY,new ByteArray(),{},target);
    if(next.control===CONTROL.OK){delivery={payload:next.payload,identity:next.identity,transfer:next.transfer,blocked:false};queued(deliver);return;}
    if(next.control!==CONTROL.EMPTY)return terminal(Error('Completion mailbox refused'));
    if(drainDocument())return;
    if(physicalInput){
      const input=kernelCall(OP.PEEK_INPUT,new ByteArray(),{},target);
      if(input.control===CONTROL.OK){
        if(input.service!==0||input.source!==0||!input.transfer||!sameIdentity(input.identity,target)
            ||!input.identity.instance||!input.identity.document||!input.identity.generation)
          return terminal(Error('Malformed physical input mailbox authority'));
        const sequence=commandSequence(input.payload);
        if(sequence<=lastCommandSequence||documentEnabled&&sequence===U64_MAX)return terminal(Error('Physical command sequence was reused, wrapped or used final document ACK headroom'));
        lastCommandSequence=sequence;
        command={payload:input.payload,identity:input.identity,transfer:input.transfer,sequence};
        executeCommand();return;
      }
      if(input.control!==CONTROL.EMPTY)return terminal(Error('Physical input mailbox refused'));
    }
    if(serviceSuspended||documentEnabled&&!documentIdle){onDirty();return;}
    if(advanceRequested){advanceRequested=false;requireOK(engineCall(ENGINE.ADVANCE));}
    onDirty();
  };
  const checkReady=()=>{
    const current=engineCall(ENGINE.CURRENT_DOCUMENT);
    if(current.control===CONTROL.OK){
      if(identity.instance===0n||identity.generation===0n||['instance','document','generation'].some(k=>current.identity[k]!==identity[k]))
        return terminal(Error('Engine document readiness differs from kernel authority'));
      state='ready';if(startTimer!==null)timer.clearTimeout(startTimer);startTimer=null;readyResolve(Object.freeze({...identity}));request();return true;
    }
    if(![CONTROL.EMPTY,CONTROL.STALE].includes(current.control))return terminal(Error('Engine refused document readiness'));
    return false;
  };
  const startupStep=()=>{
    if(state!=='starting')return;
    try{requireOK(engineCall(ENGINE.ADVANCE));if(!checkReady())timer.setTimeout(startupStep,1);}
    catch(error){fail(error);}
  };
  return Object.freeze({
    ready,closed,
    get identity(){return Object.freeze({...identity});},get state(){return state;},get depth(){return depth;},
    inspect(profile){if(state!=='new'||inspected)throw new BridgeError('Engine read-only inspection must precede kernel preparation');
      const expected=selectedProfile(profile);inspecting=true;
      try{let actual;engineCall(ENGINE.DESCRIBE,new ByteArray(),0n,identity,description=>{
          requireOK(description);actual=expected.kind==='foundation-copied-engine-editor-v1'?decodeEditorEngineFacts(description.payload):selectedProfile(decodeJSON(description.payload));
          if(Object.keys(expected).some(key=>actual[key]!==expected[key]))throw new BridgeError('Compiled engine identity differs from retained profile',{terminal:true});
        });
        inspected=actual;physicalInput=physicalProfile(actual);documentEnabled=documentProfile(actual);editorEnabled=editorProfile(actual);return actual;
      }finally{inspecting=false;}},
    configure(record){if(state!=='new'||!inspected)throw new BridgeError('Read-only engine inspection is required before kernel preparation');
      const reply=decodeRecord(kernel.call(OP.CONFIGURE,record),{kind:OP.CONFIGURE,worker:workerEpoch});requireOK(reply);
      if(reply.service!==0)return terminal(Error('Kernel preparation did not initialize its actual owner'));
      if(reply.identity.instance!==0n||reply.identity.document!==0n||reply.identity.generation!==0n)return terminal(Error('Kernel adopted an engine before native startup'));
      state='configured';return decodeJSON(reply.payload);},
    start(profile,configuration){if(state!=='configured')throw new BridgeError('Bridge is not configured');
      let selected;try{selected=selectedProfile(profile);}catch(error){if(physicalInput||documentEnabled)return terminal(error);throw error;}
      if(Object.keys(inspected).some(key=>selected[key]!==inspected[key]))return terminal(Error('Engine profile changed after read-only inspection'));
      const result=engineCall(ENGINE.START,jsonBytes(configuration),0n,identity,reply=>{
        if(reply.control!==CONTROL.OK||reply.payload.byteLength!==8)throw new BridgeError('Malformed engine startup receipt',{terminal:true});
        const data=new DataView(reply.payload.buffer),status=data.getInt32(0,true),phase=data.getUint32(4,true);
        if(status!==0||phase!==2||identity.instance===0n||reply.identity.instance!==identity.instance)
          throw new BridgeError('Engine startup failed or omitted trusted native identity adoption',{terminal:true});
      });
      if(result.control!==CONTROL.OK||result.payload.byteLength!==8)return terminal(Error('Malformed engine startup receipt'));
      const data=new DataView(result.payload.buffer),status=data.getInt32(0,true),phase=data.getUint32(4,true);
      if(status!==0||phase!==2||identity.instance===0n||result.identity.instance!==identity.instance)
        return terminal(Error('Engine did not start the exact selected native document'));
      state='starting';
      if(!checkReady()){startTimer=timer.setTimeout(()=>fail(Error('Engine document startup timed out')),startTimeout);post(startupStep);}
      return Object.freeze({...identity});},
    callback(op,pointer,length,output,capacity){
      try{
        if(state==='failed'||state==='closed')return -4;
        if(replayActive)return terminal(Error('Callback during metadata-only document replay'));
        if(inspecting)return terminal(Error('Engine performed a callback during read-only inspection'));
        if(documentCall&&(documentCall.phase!=='provider'||!documentCall.editor&&documentCall.work.kind===3||op!==OP.TURN_ENTER&&op!==OP.TURN_LEAVE&&(!documentCall.entered||documentCall.left)))
          return terminal(Error('Document callback occurred outside its permitted native turn'));
        if(op===HOST.WAKE){advanceRequested=true;request();return 0;}
        if(!active||pumping||!CALLBACK_OPS.has(op)&&![HOST.TIMER,HOST.PERSISTENCE].includes(op))return terminal(Error('Unsolicited or unsupported engine callback'));
        const maximum=op===OP.FRAME_COMMIT?MAX_FRAME+HEADER_BYTES:MAX_SERVICE+HEADER_BYTES;
        const bytes=engine.read(pointer,length,maximum);
        if(op===HOST.TIMER){
          if(bytes.byteLength!==12)return terminal(Error('Malformed engine timer'));const v=new DataView(bytes.buffer),delay=v.getFloat64(0,true),armed=v.getUint32(8,true);
          if(!Number.isFinite(delay)||delay<0||delay>86400000||armed>1)return terminal(Error('Invalid engine timer'));
          if(engineTimer!==null)timer.clearTimeout(engineTimer);engineTimer=armed?timer.setTimeout(()=>{engineTimer=null;advanceRequested=true;request();},delay):null;return 0;
        }
        if(op===HOST.PERSISTENCE){persistence=copyBytes(bytes,65536);return 0;}
        const record=decodeRecord(bytes,{kind:op,maximum,receipt:false,worker:workerEpoch});
        if(documentCall&&[OP.TURN_ENTER,OP.TURN_LEAVE].includes(op)){
          const guard=documentCall;
          if(!sameIdentity(record.identity,guard.work.identity)||record.transfer!==guard.work.transfer||record.source!==0||record.payload.byteLength
              ||op===OP.TURN_ENTER&&(guard.entered!==0||depth!==0)||op===OP.TURN_LEAVE&&(guard.entered!==1||guard.left!==0||depth!==1))
            return terminal(Error('Document native turn changed its original target/transfer or repeated entry'));
        }
        if(op===OP.TURN_ENTER&&record.transfer!==currentTransfer)return terminal(Error('Engine entered wrong delivery/ACK turn'));
        if(!integer(capacity,MAX_SERVICE+RECEIPT_BYTES)||capacity<RECEIPT_BYTES)return terminal(Error('Invalid native callback reply capacity'));
        engine.validateSpan(output,capacity);
        const raw=kernel.call(op,bytes,Math.min(capacity,MAX_SERVICE+RECEIPT_BYTES));
        const reply=decodeRecord(raw,{kind:op,worker:workerEpoch});
        if(documentCall&&[OP.TURN_ENTER,OP.TURN_LEAVE].includes(op)&&
            (!sameIdentity(reply.identity,record.identity)||reply.transfer!==record.transfer||reply.source!==0||reply.payload.byteLength))
          return terminal(Error('Kernel changed the matching document native turn receipt'));
        if(op===OP.TURN_ENTER&&reply.control===CONTROL.OK&&reply.service===0){depth++;if(documentCall)documentCall.entered++;}
        if(op===OP.TURN_LEAVE&&reply.control===CONTROL.OK&&reply.service===0){if(!depth)return terminal(Error('Native turn underflow'));depth--;if(documentCall)documentCall.left++;}
        if([OP.BEGIN_DOCUMENT,OP.BEGIN_RESOURCE_EPOCH].includes(op)&&reply.control===CONTROL.OK){
          if(!depth||reply.identity.instance===0n||identity.instance!==0n&&identity.instance!==reply.identity.instance)return terminal(Error('Forged native application identity'));
          // A prospective resource context may coexist with the current page;
          // creating it alone does not close that page or abandon its results.
          if(abandonClosedDocumentOutcomes&&op===OP.BEGIN_DOCUMENT&&metadataIdentity.generation&&!sameIdentity(metadataIdentity,reply.identity))retired.add(identityKey(metadataIdentity));
          identity={...reply.identity};if(identity.generation)lastReady={...identity};
          if(op===OP.BEGIN_DOCUMENT)metadataIdentity={...reply.identity};
          else if(metadataIdentity.instance===0n)metadataIdentity={...metadataIdentity,instance:reply.identity.instance};
        }
        if(op===OP.CLOSE_DOCUMENT&&reply.control===CONTROL.OK){
          if(abandonClosedDocumentOutcomes)retired.add(identityKey(record.identity));
          if(sameIdentity(record.identity,metadataIdentity))metadataIdentity={...metadataIdentity,document:0n,generation:0n};
          if(record.identity.document===identity.document&&record.identity.generation===identity.generation)identity={...identity,document:0n,generation:0n};
          request();
        }
        return engine.write(output,capacity,raw);
      }catch(error){fail(error);return -4;}
    },
    replayDocumentCompletion(selector){
      try{
        const selected=replaySelector(selector);
        if(state!=='ready'||!documentEnabled||active||depth||pumping||delivery||ack||command||documentCall||terminalOutcome||retirement||replayActive||replayPending)
          throw new BridgeError('Document replay requires a quiescent ready owner',{code:CONTROL.CONFLICT});
        const record=[formReplay,latestAckReplay,retirementAckReplay].find(value=>value&&value.work.kind===selected.kind
          &&value.work.sequence===selected.sequence&&value.work.transfer===selected.transfer&&sameIdentity(value.work.identity,selected.identity));
        if(!record)throw new BridgeError('No exact owned document replay record',{code:CONTROL.STALE});
        const promise=new Promise((resolve,reject)=>{replayPending={record,resolve,reject};});request();return promise;
      }catch(error){return Promise.reject(error);}
    },
    poll(){if(state!=='ready')return false;request();return true;},
    advance(){if(state!=='ready')return false;if(delivery||ack||command||documentCall||replayActive||replayPending||terminalOutcome||retirement){request();return false;}
      if(physicalInput||documentEnabled){advanceRequested=true;request();return true;}requireOK(engineCall(ENGINE.ADVANCE));request();return true;},
    retryDelivery(){if(state!=='ready'||!delivery?.blocked)throw new BridgeError('No rejected completion to retry');if(retired.has(identityKey(delivery.identity))){request();throw new BridgeError('Closed document results belong to owner retirement');}outcome(OP.DELIVERY_RESULT,delivery.transfer,RESULT.RETRY,delivery.identity);delivery.blocked=false;queued(deliver);},
    retryAck(){if(state!=='ready'||!ack?.blocked)throw new BridgeError('No rejected ACK receipt to retry');if(retired.has(identityKey(ack.identity))){request();throw new BridgeError('Closed document receipts belong to owner retirement');}outcome(OP.ACK_RECEIPT_RESULT,ack.transfer,RESULT.RETRY,ack.identity);ack.blocked=false;queued(collectAck);},
    retryTerminalOutcome(){if(!['ready','closing'].includes(state)||!terminalOutcome?.blocked)throw new BridgeError('No terminal outcome collection to retry');terminalOutcome.blocked=false;queued(abandonTerminalOutcome);},
    close(){if(state==='closed')return {graceful:true};if(state==='failed')return {graceful:false};
      if(state==='closing')return {graceful:false,pending:true};
      if(active||depth||pumping||command||documentCall||replayActive)return {graceful:false};
      clearDocumentReplays(new BridgeError('Document replay owner closed',{code:CONTROL.CLOSED}));
      try{const reply=requireOK(kernelCall(OP.CLOSE));
        if(reply.service!==0){
          if(reply.service!==2||!abandonClosedDocumentOutcomes)throw new BridgeError('Kernel still owns callbacks or resource leases');
          if(metadataIdentity.generation)retired.add(identityKey(metadataIdentity));
          metadataIdentity={...metadataIdentity,document:0n,generation:0n};identity={...identity,document:0n,generation:0n};
          state='closing';clearTimers();readyReject(Error('Engine bridge closed'));request();return {graceful:false,pending:true};
        }
        state='closed';clearTimers();readyReject(Error('Engine bridge closed'));persistence=null;closedResolve({graceful:true});return {graceful:true};}
      catch(error){fail(error);return {graceful:false};}}
  });
}
