// Focused production bootstrap tests with inert renderer data and explicit
// frontend/transport fakes. No DOM, Worker, engine, compiler or SDK is executed.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFile} from 'node:fs/promises';
import {createHash,webcrypto} from 'node:crypto';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';

const bootstrapURL=process.argv[2]?pathToFileURL(resolve(process.argv[2])):new URL('../host/appended_engine_browser_bootstrap.mjs',import.meta.url);
const bridgeURL=new URL('./engine_kernel_bridge.mjs',bootstrapURL);
const {BRIDGE_VERSION}=await import(bridgeURL.href);
if(!globalThis.crypto)Object.defineProperty(globalThis,'crypto',{value:webcrypto,configurable:true});
const encoder=new TextEncoder(),sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const abiURL=new URL('../../abi/appended/',import.meta.url);
const [contractBytes,catalogBytes,schemaBytes,headerBytes]=await Promise.all([
  'editor-v1/contract.json','editor-v1/catalog.json','editor-v1/binary-schema.json','engine_editor_protocol.h'
].map(name=>readFile(new URL(name,abiURL))));
const contract=JSON.parse(contractBytes);
const editorProfile=()=>({schema_version:1,kind:'foundation-copied-engine-editor-v1',target:'browser-wasm32',
  binding:'copied-owner-bridge/direct-worker-editor-v1',pointer_bits:32,pthread:false,shared_memory:false,
  bridge_abi:BRIDGE_VERSION,capabilities:'2035',build_sha256:'2'.repeat(64),source_recipe_sha256:'3'.repeat(64),
  contract_sha256:sha(contractBytes),provider_abi_major:1,provider_abi_minor:1,host_abi_major:1,host_abi_minor:0,
  editor_profile:contract.profile,base_header_sha256:contract.base_header_sha256,
  document_header_sha256:contract.document_header_sha256,document_contract_sha256:contract.document_contract_sha256,
  document_catalog_sha256:contract.document_catalog_sha256,physical_catalog_sha256:contract.physical_catalog_sha256,
  editor_header_sha256:sha(headerBytes),editor_catalog_sha256:sha(catalogBytes),editor_schema_sha256:sha(schemaBytes),
  document_schema_sha256:'f11fd061350f8d663dbcdec7cf0a063e4fb0ff3564d285076690f58e8a84143d',
  action_ack_schema_sha256:'1eb6c2d4f56acebc1423d9e2b5bf9a1717a99963a5c3f11f4b9d7b0fe33b50f5',
  viewport_width:800,viewport_height:600,surface_protocol_version:2,surface_capabilities:'8255',
  mouse_input_version:1,key_mapping_version:1,editor_protocol_version:1,display_scale:1,
  editor_query_max_bytes:236,editor_reply_capacity:1048576,editor_command_max_bytes:1048576});
const renderer=()=>({CHILD_SCRIPT:'inert retained editor renderer source',CHILD_SCRIPT_SHA256:'retained editor hash',
  CHILD_CSP:'retained editor policy',CHILD_SANDBOX:'allow-scripts',CHILD_PROTOCOL:'foundation-renderer-v1',CHILD_STYLE:'retained editor style'});
const protocol=()=>({validateEditorPublication:value=>value,validateEditorOperation:value=>value,validateEditorReply:value=>value});
const documentProtocol=()=>({validateDocumentState:value=>value,validateDocumentOperation:value=>value,validateDocumentReply:value=>value});
const asset=bytes=>({data:Buffer.from(bytes).toString('base64'),sha256:sha(bytes)});
const descriptor=()=>({schema_version:1,kind:'foundation-copied-engine-editor-browser',kernel_profile:'web',
  kernel_wasm_lookup:'gui_appended_engine_wasm.wasm',engine_wasm_lookup:'embedder.wasm',
  kernel_factory:asset(encoder.encode('inert retained kernel factory')),kernel_wasm:asset(new Uint8Array([0,97,115,109,1,0,0,0])),
  engine_factory:asset(encoder.encode('inert retained engine factory')),engine_wasm:asset(new Uint8Array([0,97,115,109,1,0,0,0])),
  engine_profile:editorProfile(),engine_assets:{},notices:{}});

// Published v1 logical Package/trailer layout; these identities match the
// independently retained worker fixture. The embedded author script stays data.
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
  for(const [offset,value]of [[16,prefix.length],[24,logical.length],[32,content.length],[40,indexBytes.length],[48,3]])view.setBigUint64(offset,BigInt(value),true);
  trailer.set(Buffer.from(sha(prefix),'hex'),56);trailer.set(Buffer.from(sha(logical),'hex'),88);trailer.set(Buffer.from(sha(indexBytes),'hex'),120);
  const suffix=new Uint8Array(Buffer.concat([logical,trailer]));
  return {prefix,logical,suffix,encoded:Buffer.from(suffix).toString('base64')};
}
const vector=carrier();
const dataURL=source=>'data:text/javascript;base64,'+Buffer.from(source).toString('base64');
const fixtureKey='__foundationEditorBootstrapFixture';
async function verifier(){
  const frontend=dataURL(`export function createEmbeddedFrontend(options){const state=globalThis.${fixtureKey};state.frontends.push(options);return {ready:Promise.resolve(),close(){++state.frontendCloses;}};}`);
  const transport=dataURL(`export function createWasmTransport(options){const state=globalThis.${fixtureKey};state.transports.push(options);return {ready:Promise.resolve({snapshot:{title:'Editor bootstrap fixture'}}),exchange(value){state.exchanges.push(value);return Promise.resolve({echo:value});},close(){++state.transportCloses;return Promise.resolve();}};}`);
  const channel=dataURL('export function createHostChannel(options){return options;}');
  const replace=(source,edge,target)=>{assert.equal(source.split(edge).length,2,'reviewed bootstrap import edge changed');return source.replace(edge,JSON.stringify(target));};
  let binary=await readFile(new URL('./appended_browser_bootstrap.mjs',bootstrapURL),'utf8');
  binary=replace(binary,"'./browser_embedding.mjs'",frontend);
  binary=replace(binary,"'./wasm_transport.mjs'",transport);
  let source=await readFile(bootstrapURL,'utf8');
  assert.match(source,/import \* as rendererBundle from '\.\/renderer_surface_child_bundle\.mjs';/);
  source=replace(source,"'./browser_embedding.mjs'",frontend);
  source=replace(source,"'./wasm_transport.mjs'",transport);
  source=replace(source,"'./renderer_channel.mjs'",channel);
  source=replace(source,"'./browser_surface_protocol.mjs'",new URL('./browser_surface_protocol.mjs',bootstrapURL).href);
  source=replace(source,"'./renderer_surface_child_bundle.mjs'",dataURL('export const LEGACY_RENDERER_SENTINEL=true;'));
  source=replace(source,"'./appended_browser_bootstrap.mjs'",dataURL(binary));
  source=replace(source,"'./engine_kernel_bridge.mjs'",bridgeURL.href);
  return import(dataURL(source));
}
const {startAppendedEngineBrowser:start,verifyEngineSuffix}=await verifier();
function hostFixture({payload=null,onDOM=()=>{}}={}){
  const state={frontends:[],transports:[],exchanges:[],frontendCloses:0,transportCloses:0,domReads:0,workers:0,urls:[],revoked:[]};
  globalThis[fixtureKey]=state;
  const listeners=new Map(),status={textContent:''},mount={},node=()=>({append(){}});
  const document={querySelector:name=>name==='#status'?status:name==='#application'?mount:null,
    querySelectorAll:()=>payload===null?[]:[{getAttribute:()=> 'application/octet-stream',textContent:payload}],
    createElement:node,body:node()};
  const host={addEventListener:(name,handler)=>listeners.set(name,handler),removeEventListener:name=>listeners.delete(name),
    URL:{createObjectURL(){const value='blob:editor-bootstrap-fixture-'+(state.urls.length+1);state.urls.push(value);return value;},revokeObjectURL:value=>state.revoked.push(value)},
    Blob:class{constructor(parts,options){this.parts=parts;this.options=options;}},crypto:webcrypto,
    Worker:class{constructor(){++state.workers;throw Error('No Worker is permitted in this bootstrap fixture');}}};
  Object.defineProperty(host,'document',{get(){++state.domReads;onDOM();return document;}});
  return {host,state,listeners,status,document};
}
const args=(f,extra={})=>({prefix:vector.prefix,kernel:descriptor(),workerSource:'inert retained Worker source',
  editorRendererBundle:renderer(),editorProtocol:protocol(),host:f.host,...extra});
const assertUnstarted=f=>{assert.equal(f.state.frontends.length,0);assert.equal(f.state.transports.length,0);assert.equal(f.state.workers,0);assert.equal(f.state.urls.length,0);assert.equal(f.listeners.size,0);};

test('explicit editor kind accepts the complete38-field profile and remains idle without a payload',async()=>{
  const f=hostFixture();
  try{
    assert.equal(Object.keys(editorProfile()).length,38);
    const result=await start(args(f));
    assert.equal(typeof result.close,'function');assert.equal(f.status.textContent,'No appended application payload is attached.');
    assert.ok(f.state.domReads>0);assertUnstarted(f);
  }finally{delete globalThis[fixtureKey];}
});

test('editor requires its own six-field renderer data before DOM and rejects getters without fallback',async()=>{
  const valid=renderer();let getters=0;
  const accessor={...valid};Object.defineProperty(accessor,'CHILD_SCRIPT',{enumerable:true,get(){++getters;return 'not owned';}});
  const missing={...valid};delete missing.CHILD_SCRIPT;
  const inherited=Object.assign(Object.create(valid),{a:'1',b:'2',c:'3',d:'4',e:'5',f:'6'});
  for(const value of [null,{},missing,{...valid,extra:'unreviewed'},{...valid,CHILD_STYLE:1},accessor,inherited,{...valid,[Symbol('extra')]:'unreviewed'}]){
    const f=hostFixture();
    try{
      await assert.rejects(start(args(f,{editorRendererBundle:value,physicalRendererBundle:valid})),/renderer bundle/);
      assert.equal(f.state.domReads,0);assertUnstarted(f);
    }finally{delete globalThis[fixtureKey];}
  }
  assert.equal(getters,0);
});

test('editor requires three owned protocol functions before DOM and never evaluates accessors',async()=>{
  const valid=protocol();let getters=0;
  const accessor={...valid};Object.defineProperty(accessor,'validateEditorReply',{enumerable:true,get(){++getters;return valid.validateEditorReply;}});
  const missing={...valid};delete missing.validateEditorOperation;
  for(const value of [null,{},missing,{...valid,extra:()=>{}},{...valid,[Symbol('extra')]:()=>{}},{...valid,validateEditorReply:1},accessor,Object.create(valid)]){
    const f=hostFixture();
    try{
      await assert.rejects(start(args(f,{editorProtocol:value})),/editor channel protocol/);
      assert.equal(f.state.domReads,0);assertUnstarted(f);
    }finally{delete globalThis[fixtureKey];}
  }
  assert.equal(getters,0);
});

test('optional document capability captures three owned functions before DOM and rejects accessors',async()=>{
  const valid=documentProtocol();let getters=0;const accessor={...valid};Object.defineProperty(accessor,'validateDocumentReply',{enumerable:true,get(){++getters;return valid.validateDocumentReply;}});
  const missing={...valid};delete missing.validateDocumentState;
  for(const value of [{},missing,{...valid,extra:()=>{}},{...valid,[Symbol('extra')]:()=>{}},{...valid,validateDocumentOperation:1},accessor,Object.create(valid)]){
    const f=hostFixture();try{await assert.rejects(start(args(f,{documentProtocol:value})),/document channel protocol/);assert.equal(f.state.domReads,0);assertUnstarted(f);}finally{delete globalThis[fixtureKey];}
  }
  assert.equal(getters,0);
});

test('strict editor facts and explicit descriptor kinds reject profile mixing without a fallback',async()=>{
  const changes=[k=>{k.engine_profile.kind='foundation-copied-engine-document-v2';},
    k=>{k.engine_profile.capabilities='2003';},k=>{k.engine_profile.surface_protocol_version=1;},
    k=>{k.engine_profile.editor_query_max_bytes=237;},k=>{k.engine_profile.editor_header_sha256='0'.repeat(64);},
    k=>{k.engine_profile.display_scale=true;},k=>{delete k.engine_profile.editor_schema_sha256;},
    k=>{k.engine_profile.extra=1;},k=>{k.kind='foundation-copied-engine-browser';},
    k=>{k.kind='foundation-copied-engine-physical-browser';},k=>{k.kind='foundation-copied-engine-document-browser';}];
  for(const change of changes){
    const f=hostFixture(),kernel=descriptor();change(kernel);
    try{
      await assert.rejects(start(args(f,{kernel,physicalRendererBundle:renderer()})),/Unsupported/);
      assertUnstarted(f);assert.match(f.status.textContent,/Unsupported/);
    }finally{delete globalThis[fixtureKey];}
  }
});

test('golden carrier selects editor-v1 validation and captures inert renderer and protocol before frontend injection',async()=>{
  assert.equal(vector.logical.length,898);
  assert.equal(sha(vector.logical),'1ed1604ba024ccc7203b378c7d9cf5817f5f91e38186851e1f9dd6d6d336c3d4');
  assert.equal(sha(vector.suffix),'9a97367565f6ff0c628d474342ad8da695e89d36ffc93ce4e60f09d94f4fc55b');
  const prepared=await verifyEngineSuffix(vector.encoded,vector.prefix);
  assert.deepEqual(prepared.suffix,vector.suffix);assert.equal(prepared.prefixSha256,sha(vector.prefix));
  const suppliedRenderer=renderer(),originalRenderer={...suppliedRenderer},suppliedProtocol=protocol(),originalProtocol={...suppliedProtocol},suppliedDocumentProtocol=documentProtocol(),originalDocumentProtocol={...suppliedDocumentProtocol};
  let changed=false;
  const f=hostFixture({payload:vector.encoded,onDOM(){if(changed)return;changed=true;
    suppliedRenderer.CHILD_SCRIPT='changed after capture';suppliedProtocol.validateEditorOperation=()=>{throw Error('Changed after capture');};suppliedDocumentProtocol.validateDocumentOperation=()=>{throw Error('Changed after document capture');};}});
  try{
    const result=await start(args(f,{editorRendererBundle:suppliedRenderer,editorProtocol:suppliedProtocol,documentProtocol:suppliedDocumentProtocol}));
    assert.equal(f.state.frontends.length,1);assert.equal(f.state.transports.length,1);assert.equal(f.state.workers,0);
    const options=f.state.frontends[0],channel=options.channelFactory({fixture:'owned'});
    assert.equal(channel.fixture,'owned');assert.deepEqual(options.rendererBundle,originalRenderer);assert.notEqual(options.rendererBundle,suppliedRenderer);
    assert.ok(Object.isFrozen(options.rendererBundle));assert.equal(Object.getPrototypeOf(options.rendererBundle),Object.prototype);
    assert.deepEqual(channel.editorProtocol,originalProtocol);assert.notEqual(channel.editorProtocol,suppliedProtocol);assert.ok(Object.isFrozen(channel.editorProtocol));
    assert.deepEqual(channel.documentProtocol,originalDocumentProtocol);assert.notEqual(channel.documentProtocol,suppliedDocumentProtocol);assert.ok(Object.isFrozen(channel.documentProtocol));
    for(const name of Object.keys(originalDocumentProtocol)){const value={name};assert.equal(channel.documentProtocol[name](value),value);}
    for(const name of Object.keys(originalProtocol)){const value={name};assert.equal(channel.editorProtocol[name](value),value);}
    const connect={type:'surfaceConnect',version:2,profile:'editor_v1',supported:'8255',mouseInputVersion:1};
    assert.equal(channel.surfaceProtocol.validateSurfaceOperation(connect,null,null),connect);
    assert.throws(()=>channel.surfaceProtocol.validateSurfaceOperation({type:'surfaceConnect',version:1,supported:'8225',mouseInputVersion:1},null,null));
    const surface={version:2,profile:'editor_v1',capabilities:{version:1,supported:'8255',mouseInputVersion:1,
      limits:{textBytes:65536,clipboardBytes:65536,popupItems:1024,popupTextBytes:65536,captureRules:64,heldKeys:64,popupDepth:8}},
      presentation:null,focused:false,active:true,composition:null,lastSequence:'0',serviceActive:false};
    assert.equal(channel.surfaceProtocol.validateSurfaceState(null,surface),surface);
    const legacy=structuredClone(surface);delete legacy.profile;legacy.version=1;
    assert.throws(()=>channel.surfaceProtocol.validateSurfaceState(null,legacy));
    assert.deepEqual(await options.exchange({opaque:'fixture'}),{echo:{opaque:'fixture'}});
    assert.equal(f.document.title,'Editor bootstrap fixture');assert.equal(f.status.textContent,'Editor bootstrap fixture');
    result.close();result.close();assert.equal(f.state.frontendCloses,1);assert.equal(f.state.transportCloses,1);
    assert.equal(f.listeners.size,0);assert.deepEqual(f.state.revoked,f.state.urls);
    assert.equal(globalThis.engineFixtureApplicationRan,undefined);
  }finally{delete globalThis[fixtureKey];}
});

test('an older editor carrier keeps document protocol absent when it was not provided',async()=>{const f=hostFixture({payload:vector.encoded});try{const result=await start(args(f));const channel=f.state.frontends[0].channelFactory({});assert.equal(Object.hasOwn(channel,'documentProtocol'),false);result.close();}finally{delete globalThis[fixtureKey];}});
