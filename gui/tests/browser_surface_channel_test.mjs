// SPDX-License-Identifier: CC0-1.0
import assert from 'node:assert/strict';
import {MessageChannel} from 'node:worker_threads';
import {pathToFileURL} from 'node:url';
const {validateRendererOperation,createHostChannel,createRendererRequests}=await import(pathToFileURL(process.argv[2]));
const {Client}=await import(pathToFileURL(process.argv[3]));
const surfaceProtocol=await import(process.argv[4]?pathToFileURL(process.argv[4]):new URL('../host/browser_surface_protocol.mjs',import.meta.url));
const protocol='foundation-renderer-v1',generation='surface-channel-fixture';
const clone=value=>structuredClone(value);
const flush=async()=>{for(let index=0;index<10;++index)await new Promise(resolve=>setImmediate(resolve));};
const scheduler=()=>{let next=0;const timers=new Map();return {timers,setTimeout(callback){timers.set(++next,callback);return next;},clearTimeout(id){timers.delete(id);}};};
const owner={id:'surface',generation:'9007199254740993'};
const snapshot=(revision='9007199254740993')=>({revision,title:'Channel fixture',palette:{},width:200,height:100,scale:1,
  pages:[],activePage:null,widgets:[{key:clone(owner),kind:2,visible:true,enabled:true,inModal:true,bounds:[0,0,200,100],clip:[0,0,200,100],
    pointerInput:false,contextInput:false,options:[],actions:[],records:[]}],measurements:[],keyBindings:[],focus:null,popup:null,closed:false});
const surface=(revision='9007199254740993')=>({version:1,capabilities:{version:1,supported:'97',limits:{
  textBytes:65536,clipboardBytes:65536,popupItems:1024,popupTextBytes:65536,captureRules:64,heldKeys:64,popupDepth:8}},
  presentation:{identity:{owner:clone(owner),presentationRevision:revision,generation:'3',epoch:'4',context:'5'},required:'97',
    bounds:[0,0,200,100],clip:[0,0,200,100],displayScale:1,available:true,keys:{fallback:'pass',rules:[]},editor:null,clipboard:null,popup:null},
  focused:true,active:true,composition:null,lastSequence:'0',serviceActive:false});
const state=(ack=0,profile=true)=>({epoch:'surface-session',ack:String(ack),snapshot:snapshot(),service:null,error:'',...(profile?{surface:surface()}:{})});
const input=(sequence='1',kind='key')=>({type:'surfaceInput',identity:surface().presentation.identity,sequence,
  input:kind==='key'?{kind:'key',phase:'down',key:'a',code:'KeyA',location:0,modifiers:0,repeat:false}:
    kind==='focus'?{kind:'focus',focused:true,active:true,cause:'direct'}:
      {kind:'pointer',phase:'move',pointer:'0',x:10,y:20,wheelX:0,wheelY:0,button:0,buttons:0,clicks:1,modifiers:0}});
const reply=(current,envelope)=>{
  const next=clone(current);next.ack=envelope.seq;
  if(envelope.operation.type==='surfaceConnect'){next.surface=surface();next.surface.focused=false;}
  if(envelope.operation.type==='surfaceInput'){
    next.surface.lastSequence=envelope.operation.sequence;
    if(envelope.operation.input.kind==='focus'){
      next.surface.focused=envelope.operation.input.focused;next.surface.active=envelope.operation.input.active;
    }
  }
  return next;
};
async function fixture({initial=state(),hook=true,exchange}={}){
  const ports=new MessageChannel(),clock=scheduler(),accepted=[],painted=[],failures=[],wire=[],sent=[];
  let host,renderer;
  const client=new Client(async envelope=>{sent.push(clone(envelope));return exchange?exchange(envelope,client):reply(client.state,envelope);},value=>host?.accept(value));
  const failure=(side,error)=>{failures.push({side,error});renderer?.close(error);client.close();};
  client.accept(initial);
  host=createHostChannel({port:ports.port1,generation,client,scheduler:clock,onBound:()=>host.accept(client.state),
    onFailure:error=>failure('host',error),...(hook?{surfaceProtocol}:{})});
  ports.port2.addEventListener('message',event=>wire.push(event.data));
  renderer=createRendererRequests({port:ports.port2,generation,acceptSnapshot:(...args)=>accepted.push(args),present:(...args)=>painted.push(args),
    onFailure:error=>failure('child',error),...(hook?{surfaceProtocol}:{})});
  const close=()=>{host.close();renderer.close();client.close();ports.port1.close();ports.port2.close();assert.equal(clock.timers.size,0);};
  await flush();
  return {ports,clock,accepted,painted,failures,wire,sent,client,host,renderer,close};
}
const stale=promise=>assert.rejects(promise,error=>error instanceof Error&&error.stale===true);

// The optional hook must not extend the ordinary channel's vocabulary or wire.
{
  const connect={type:'surfaceConnect',version:1,supported:'97'};
  assert.throws(()=>validateRendererOperation(connect,snapshot()),/delegated/);
  assert.throws(()=>validateRendererOperation(connect,snapshot(),null),/delegated/);
  assert.equal(validateRendererOperation(connect,snapshot(),null,surfaceProtocol),connect);
  assert.equal(validateRendererOperation(input(),snapshot(),surface(),surfaceProtocol).sequence,'1');
  const f=await fixture({initial:state(0,false),hook:false});
  try{
    assert.deepEqual(Object.keys(f.wire.find(message=>message.type==='state')).sort(),
      ['protocol','type','generation','revision','snapshot','barrier','cancelPointers'].sort());
    assert(f.accepted.every(args=>args.length===2));assert(f.painted.every(args=>args.length===2));
    await f.renderer.send({type:'activate',key:owner});
    assert.equal(f.sent.length,1);assert.equal(f.failures.length,0);
    assert(f.wire.filter(message=>message.type==='state').every(message=>!Object.hasOwn(message,'surface')));
  }finally{f.close();}
  const disabled=state();disabled.surface=null;
  const legacy=await fixture({initial:disabled,hook:false});
  try{assert.equal(legacy.failures.filter(value=>value.side==='host').length,1);assert.equal(legacy.accepted.length,0);assert.equal(legacy.sent.length,0);}
  finally{legacy.close();}
}

// An explicit null companion enables handshake; accepted pairs precede results.
{
  const initial=state();initial.surface=null;
  const f=await fixture({initial});
  try{
    const first=f.wire.find(message=>message.type==='state');assert(Object.hasOwn(first,'surface'));assert.equal(first.surface,null);
    await f.renderer.send({type:'surfaceConnect',version:1,supported:'97'}).then(()=>{
      const accepted=f.accepted.at(-1);assert.equal(accepted.length,4);assert.equal(accepted[3],true);
      assert.equal(accepted[2].capabilities.supported,'97');assert.equal(accepted[2].presentation.identity.presentationRevision,accepted[0].revision);
    });
    assert.equal(f.painted.at(-1).length,4);assert.equal(f.painted.at(-1)[3],true);
    await f.renderer.send(input('1','focus'));
    await f.renderer.send(input('3')).then(()=>assert.equal(f.accepted.at(-1)[2].lastSequence,'3'));
    assert.deepEqual(f.sent.map(envelope=>envelope.operation.type),['surfaceConnect','surfaceInput','surfaceInput']);
    assert.equal(f.sent[2].operation.identity.owner.generation,'9007199254740993');
    assert.equal(f.failures.length,0);
  }finally{f.close();}
}

// Receipt and Client first-dispatch checks use the exact current companion.
{
  const f=await fixture();
  try{
    f.client.failed=true;
    const pending=f.renderer.send(input()).catch(error=>error);await flush();assert.equal(f.client.queue.length,1);
    const replacement=state();replacement.snapshot.revision='9007199254740994';
    replacement.surface.presentation.identity.presentationRevision=replacement.snapshot.revision;replacement.surface.presentation.identity.context='6';
    f.client.accept(replacement);f.client.retry();
    const error=await pending;assert.equal(error.stale,true);assert.match(error.message,/identity|replaced/i);
    assert.equal(f.accepted.at(-1)[2].presentation.identity.context,'6','Replacement must be accepted before stale completion');
    assert.equal(f.sent.length,0);assert.equal(f.client.ack,0n);assert.equal(f.client.inflight,null);assert.equal(f.client.queuedBytes,0);
    assert.equal(f.failures.length,0);
  }finally{f.close();}
}

// Typed surface moves retain separate order and the caller's original identity.
{
  const f=await fixture();
  try{
    f.client.failed=true;
    const first=input('1','pointer'),second=input('2','pointer');second.input.x=30;
    const one=f.renderer.send(first),two=f.renderer.send(second);
    first.identity.context='99';first.input.x=999;second.identity.owner.id='other';second.input.x=888;
    await flush();assert.equal(f.client.queue.length,2,'Surface events must not coalesce');f.client.retry();await Promise.all([one,two]);
    assert.equal(f.sent.length,2);assert.deepEqual(f.sent.map(value=>value.operation.input.x),[10,30]);
    assert(f.sent.every(value=>value.operation.identity.context==='5'&&value.operation.identity.owner.id==='surface'));
    assert.deepEqual(f.sent.map(value=>value.operation.sequence),['1','2']);assert.equal(f.failures.length,0);
  }finally{f.close();}
}

// Once delivery is uncertain, retry keeps the complete prepared envelope.
{
  let uncertain=true;const bytes=[];
  const f=await fixture({exchange:(envelope,client)=>{bytes.push(JSON.stringify(envelope));if(uncertain)throw Error('uncertain delivery');return reply(client.state,envelope);}});
  try{
    const original=input(),pending=f.renderer.send(original);await flush();assert.equal(f.client.failed,true);
    original.identity.context='99';original.input.key='b';
    const replacement=state();replacement.snapshot.revision='9007199254740994';
    replacement.surface.presentation.identity.presentationRevision=replacement.snapshot.revision;replacement.surface.presentation.identity.context='6';
    f.client.accept(replacement);await flush();
    uncertain=false;f.client.retry();await pending;
    assert.equal(bytes.length,2);assert.equal(bytes[0],bytes[1]);assert.equal(f.client.ack,1n);assert.equal(f.failures.length,0);
    assert.equal(f.accepted.at(-1)[2].presentation.identity.context,'6','Retry must not reinstall its retired presentation');
  }finally{f.close();}
}

// Ordinary stale conditions reject without exchange, ack advance or channel loss.
for(const change of [
  value=>{value.surface.lastSequence='1';},value=>{value.surface.serviceActive=true;value.service={id:'7',kind:2};},
  value=>{value.surface.focused=false;},value=>{value.surface.active=false;},
  value=>{value.surface.presentation.available=false;}
]){
  const initial=state();change(initial);const f=await fixture({initial});
  try{await stale(f.renderer.send(input()));assert.equal(f.sent.length,0);assert.equal(f.client.ack,0n);assert.equal(f.failures.length,0);}
  finally{f.close();}
}

// A negotiated profile cannot appear or disappear after the first host state.
for(const profile of [false,true]){
  const f=await fixture({initial:state(0,profile)});
  try{
    const before=f.accepted.length,bad=state(0,!profile);
    try{f.host.accept(bad);}catch{}
    await flush();assert.equal(f.failures.filter(value=>value.side==='host').length,1);assert.equal(f.accepted.length,before);
    assert.equal(f.sent.length,0);
  }finally{f.close();}
}

// Invalid authoritative pairs never reach a child callback or state acknowledgment.
const badPairs=[
  value=>{delete value.surface.focused;},value=>{value.surface.focused='true';},
  value=>{value.surface.presentation.identity.presentationRevision='2';},
  value=>{value.surface.presentation.identity.owner.generation='2';},value=>{value.surface.presentation.bounds[0]=1;},
  value=>{value.surface.serviceActive=1;},value=>{value.service={id:'7',kind:2};}
];
for(const change of badPairs){
  const f=await fixture();
  try{
    const before=f.accepted.length,bad=state();change(bad);
    try{f.host.accept(bad);}catch{}
    await flush();assert.equal(f.failures.filter(value=>value.side==='host').length,1);assert.equal(f.accepted.length,before);
  }finally{f.close();}
}
{
  const f=await fixture();
  try{
    const native=state();native.surface.serviceActive=true;f.client.accept(native);
    await flush();assert.equal(f.failures.length,0);assert.equal(f.accepted.at(-1)[2].serviceActive,true);
    await assert.rejects(f.renderer.send(input()),error=>error.stale===true);
    await assert.rejects(f.renderer.send({type:'activate',key:owner}),error=>error.stale===true);
    assert.equal(f.sent.length,0,'Trusted native service allowed a typed key without a legacy descriptor');
  }finally{f.close();}
}
for(const [firstProfile,nextProfile,change,hook] of [
  [true,true,badPairs[0],true],[true,true,badPairs[1],true],[true,true,badPairs[2],true],
  [true,false,()=>{},true],[false,true,()=>{},true],[false,true,()=>{},false]
]){
  const ports=new MessageChannel(),accepted=[],painted=[],failures=[],received=[];
  ports.port1.onmessage=event=>received.push(event.data);ports.port1.start();
  const renderer=createRendererRequests({port:ports.port2,generation,acceptSnapshot:(...args)=>accepted.push(args),present:(...args)=>painted.push(args),
    onFailure:error=>failures.push(error),...(hook?{surfaceProtocol}:{})});
  const send=(revision,value)=>ports.port1.postMessage({protocol,type:'state',generation,revision,snapshot:value.snapshot,barrier:false,cancelPointers:false,
    ...(Object.hasOwn(value,'surface')?{surface:value.surface}:{})});
  try{
    await flush();send('1',state(0,firstProfile));await flush();const before=accepted.length,acks=received.filter(value=>value.type==='stateAck').length;
    const bad=state(0,nextProfile);change(bad);send('2',bad);await flush();
    assert.equal(failures.length,1);assert.equal(accepted.length,before);assert.equal(painted.length,before);
    assert.equal(received.filter(value=>value.type==='stateAck').length,acks);
  }finally{renderer.close();ports.port1.close();ports.port2.close();}
}

// Untrusted focus cannot acquire the host-only service/popup vocabulary.
for(const cause of ['owned_service','owned_popup']){
  const f=await fixture();
  try{
    const forged=input('1','focus');forged.input.cause=cause;
    const pending=f.renderer.send(forged).catch(error=>error);await flush();
    assert.equal(f.failures.filter(value=>value.side==='host').length,1);assert.equal(f.sent.length,0);assert.equal(f.client.ack,0n);
    f.renderer.close();await pending;
  }finally{f.close();}
}
console.log('Browser surface channel: legacy compatibility, explicit profile, paired acceptance, first-dispatch guards, immutable ordering/retry and fatal malformed boundaries passed');
