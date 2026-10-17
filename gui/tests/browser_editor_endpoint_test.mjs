import assert from 'node:assert/strict';
import {test} from 'node:test';
import {MessageChannel} from 'node:worker_threads';
import {validateEditorPublication,validateEditorOperation,validateEditorReply,createBrowserEditorEndpoint} from '../host/browser_editor_endpoint.mjs';
import {captureEditorText} from '../host/browser_surface_editor_text.mjs';
import {validateSurfaceState,validateSurfaceOperation} from '../host/browser_surface_protocol.mjs';
import {createHostChannel,createRendererRequests} from '../host/renderer_channel.mjs';
import {Client} from '../host/browser_client.mjs';

const clone=structuredClone,wide='18446744073709551615';
const protocol={validateEditorPublication,validateEditorOperation,validateEditorReply};
const surfaceProtocol={validateSurfaceState:(s,p)=>validateSurfaceState(s,p,'editor_v1'),validateSurfaceOperation:(o,s,p)=>validateSurfaceOperation(o,s,p,'editor_v1')};
function frame(token='9007199254741001',revision='9007199254741002',selection=[3,3]){
  const identity={owner:{id:'surface',generation:wide},presentationRevision:wide,generation:'7',epoch:'11',context:'13'};
  const widget={key:clone(identity.owner),visible:true,enabled:true,inModal:true,bounds:[0,0,100,100],clip:[0,0,100,100]};
  const snapshot={revision:wide,title:'Editor',palette:{},scale:1,width:100,height:100,closed:false,widgets:[widget],pages:[],activePage:null,measurements:[],keyBindings:[],commands:[],focus:widget.key,popup:null};
  const basis={token,identity:clone(identity),editorRevision:revision,surrounding:'abc',selection,backward:false,composition:'0'};
  const surface={version:2,profile:'editor_v1',capabilities:{version:1,supported:'8255',mouseInputVersion:1,limits:{textBytes:65536,clipboardBytes:65536,popupItems:1024,popupTextBytes:65536,captureRules:64,heldKeys:64,popupDepth:8}},presentation:{identity,required:'8255',bounds:[0,0,100,100],clip:[0,0,100,100],displayScale:1,available:true,keys:{fallback:'pass',rules:[]},editor:{revision,compositionTransaction:'0',surrounding:'abc',selection:clone(selection),selectionBackward:false,caret:[0,0,1,15],editable:true,inputPurpose:'normal'},clipboard:null,popup:null},focused:true,active:true,composition:null,lastSequence:'0',serviceActive:false};
  return {snapshot,surface,basis,publication:{basis:clone(basis),settlement:null,composition:null,retirement:null}};
}
function packet(f=frame()){
  return {type:'editorObservation',session:wide,basis:clone(f.basis),defaultToken:null,defaultDependencies:[],observation:{id:'1',predecessor:null,kind:'key',authority:'native',group:'1',groupEnd:true,transaction:'0',before:captureEditorText({value:'abc',selectionStart:3,selectionEnd:3,selectionDirection:'forward'}),after:null,data:{phase:'down',key:'ArrowLeft',code:'ArrowLeft',location:0,modifiers:0,repeat:false,isComposing:false}}};
}
function receipt(p,next=frame('9007199254741003','9007199254741004',[2,2])){
  return {session:p.session,id:p.observation.id,predecessor:p.observation.predecessor,submittedToken:p.basis.token,outcome:'applied',basis:clone(next.basis),continuity:'same',defaultToken:null,composition:null,retirement:null};
}
function fixture({nulls=0,maxPolls=64,pair=true,ticket='17',revoke=false}={}){
  let current=frame(),sequence=0n,takes=0,endpoint;const operations=[],errors=[];
  const p=packet(current),next=frame('9007199254741003','9007199254741004',[2,2]),r=receipt(p,next);
  endpoint=createBrowserEditorEndpoint({maxPolls,onFailure:error=>errors.push(error),send:async operation=>{
    operations.push(clone(operation));const type=operation.type,seq=String(++sequence);let reply;
    if(type==='editorSubmit'||type==='editorRevoke')reply={type,sequence:seq,ticket};
    else if(type==='editorResync')reply={type,sequence:seq};
    else{
      ++takes;
      reply={type,sequence:seq,ticket:operation.ticket,completion:takes<=nulls?null:{ticket:operation.ticket,admission:'completed',receipt:revoke?null:r,detail:''}};
      if(reply.completion?.receipt){current=next;current.publication={basis:clone(next.basis),settlement:{session:r.session,id:r.id,predecessor:r.predecessor,submittedToken:r.submittedToken},composition:null,retirement:null};}
    }
    if(pair)endpoint.accept(current.snapshot,current.surface,current.publication,reply);
    return reply;
  }});
  endpoint.accept(current.snapshot,current.surface,current.publication);
  return {endpoint,operations,errors,p,next,r,current:()=>current};
}

test('endpoint owns exact accepted full-u64 basis without minting or caller mutation',()=>{
  const f=fixture(),first=f.current(),resolved=f.endpoint.resolveBasis(first.snapshot,first.surface);
  assert.equal(resolved.basis.identity.owner.generation,wide);assert(Object.isFrozen(resolved.basis));
  first.publication.basis.token='1';assert.notEqual(f.endpoint.resolveBasis(first.snapshot,first.surface).basis.token,'1');
  assert.equal(f.endpoint.resolveBasis({...first.snapshot,revision:'9'},first.surface),null);f.endpoint.close();
});
test('accepted fractional presentation geometry is retained while editor offsets remain integers',()=>{
  const f=frame();f.snapshot.scale=f.surface.presentation.displayScale=1.5;
  f.snapshot.widgets[0].bounds=f.surface.presentation.bounds=[0.25,0.5,100.5,100.25];
  f.snapshot.widgets[0].clip=f.surface.presentation.clip=[0.25,0.5,100.5,100.25];
  f.surface.presentation.editor.caret=[2.25,0.5,1,14.5];
  const endpoint=createBrowserEditorEndpoint({send:async()=>assert.fail('No dispatch')});
  endpoint.accept(f.snapshot,f.surface,f.publication);assert.deepEqual(endpoint.resolveBasis(f.snapshot,f.surface).basis,f.basis);
  const p=clone(packet(f));p.observation.before.selectionStart=1.5;
  assert.throws(()=>validateEditorOperation({type:'editorSubmit',packet:p},f.snapshot,f.surface,f.publication));endpoint.close();
});
test('strict packet shapes and accessor descriptors fail before sending',()=>{
  const f=frame();let reads=0;const publication=clone(f.publication);
  Object.defineProperty(publication,'basis',{enumerable:true,get(){++reads;return f.basis;}});
  assert.throws(()=>validateEditorPublication(f.snapshot,f.surface,publication));assert.equal(reads,0);
  for(const change of [p=>p.extra=true,p=>p.session=1,p=>p.observation.before.byteLength=1,p=>p.observation.data.extra=true]){
    const p=clone(packet(f));change(p);assert.throws(()=>validateEditorOperation({type:'editorSubmit',packet:p},f.snapshot,f.surface,f.publication));
  }
});
test('one queue submission followed only by bounded ticket takes',async()=>{
  const f=fixture({nulls:2});assert.deepEqual(await f.endpoint.sendObservation(f.p),f.r);
  assert.deepEqual(f.operations.map(o=>o.type),['editorSubmit','editorTake','editorTake','editorTake']);
  assert.equal(f.operations.filter(o=>o.type==='editorSubmit').length,1);assert(f.operations.slice(1).every(o=>o.ticket==='17'));f.endpoint.close();
});
test('reply without a previously accepted paired state is refused',async()=>{
  const f=fixture({pair:false});await assert.rejects(f.endpoint.sendObservation(f.p),/paired state/);assert.equal(f.operations.length,1);assert.equal(f.errors.length,1);
});
test('null admission ticket never causes resubmission or a take',async()=>{
  const f=fixture({ticket:null});await assert.rejects(f.endpoint.sendObservation(f.p),/not admitted/);assert.deepEqual(f.operations.map(o=>o.type),['editorSubmit']);
});
test('poll budget exhaustion stops without resubmitting',async()=>{
  const f=fixture({nulls:10,maxPolls:2});await assert.rejects(f.endpoint.sendObservation(f.p),/budget exhausted/);
  assert.deepEqual(f.operations.map(o=>o.type),['editorSubmit','editorTake','editorTake']);assert.equal(f.errors.length,1);
});
test('closing the endpoint cancels a pending poll and dispatches no further take',async()=>{
  const f=frame(),calls=[],timers=new Map();let sequence=0,endpoint;
  const scheduler={setTimeout(fn){const id=Symbol();timers.set(id,fn);return id;},clearTimeout(id){timers.delete(id);}};
  endpoint=createBrowserEditorEndpoint({scheduler,send:async operation=>{
    calls.push(operation.type);const reply={type:operation.type,sequence:String(++sequence),ticket:'17',...(operation.type==='editorTake'?{completion:null}:{})};
    endpoint.accept(f.snapshot,f.surface,f.publication,reply);return reply;
  }});
  endpoint.accept(f.snapshot,f.surface,f.publication);
  const pending=endpoint.sendObservation(packet(f));await new Promise(resolve=>setImmediate(resolve));
  assert.equal(timers.size,1);endpoint.close();await assert.rejects(pending,/closed/);
  assert.equal(timers.size,0);assert.deepEqual(calls,['editorSubmit','editorTake']);
});
test('service retirement permits metadata only, and a closed state stops all dispatch',()=>{
  const f=frame();f.surface.serviceActive=true;
  const record={reason:'Service',basis:clone(f.basis),composition:null,keys:[],incarnation:'9'};
  for(const operation of [{type:'editorTake',ticket:'17'},{type:'editorRevoke',record},{type:'editorResync'}])
    assert.deepEqual(validateEditorOperation(operation,f.snapshot,f.surface,f.publication),operation);
  assert.throws(()=>validateEditorOperation({type:'editorSubmit',packet:packet(f)},f.snapshot,f.surface,f.publication),error=>error.stale===true);
  for(const operation of [{type:'editorTake',ticket:'17'},{type:'editorRevoke',record},{type:'editorResync'}])
    assert.throws(()=>validateEditorOperation(operation,{...f.snapshot,closed:true},f.surface,f.publication),error=>error.stale===true);
});
test('completed revocation with no receipt grants no new basis',async()=>{
  const f=fixture({revoke:true});const record={reason:'Blur',basis:clone(f.p.basis),composition:null,keys:[],incarnation:'9'};
  const value=await f.endpoint.revoke(record);assert.equal(value.receipt,null);assert.equal(value.admission,'completed');
  assert.deepEqual(f.operations.map(o=>o.type),['editorRevoke','editorTake']);f.endpoint.close();
});
test('reply sequence/type/ticket and completion schemas stay exact',()=>{
  const reply={type:'editorTake',sequence:wide,ticket:'19',completion:null};assert.equal(validateEditorReply(reply,{type:'editorTake',ticket:'19'},wide).sequence,wide);
  for(const bad of [{...reply,sequence:1},{...reply,ticket:'20'},{...reply,extra:true},{...reply,completion:{ticket:'19',admission:'invented',receipt:null,detail:''}}])assert.throws(()=>validateEditorReply(bad,{type:'editorTake',ticket:'19'},wide));
});
test('known null retirement remains an owned proof and cannot grant a basis',()=>{
  const f=frame();f.surface.presentation.editor=null;
  for(const [availability,authorityRetired] of [['noneditable',false],['unavailable',false],['available',true]]){
    const retirement={availability,identity:clone(f.basis.identity),observationRevision:wide,readbackAttested:true,...(authorityRetired?{authorityRetired:true}:{})};
    const publication={basis:null,settlement:{session:wide,id:'1',predecessor:null,submittedToken:f.basis.token},composition:null,retirement};
    const endpoint=createBrowserEditorEndpoint({send:async()=>assert.fail('No operation')});endpoint.accept(f.snapshot,f.surface,publication);
    assert.deepEqual(endpoint.resolveBasis(f.snapshot,f.surface),{basis:null,settlement:publication.settlement,retirement});endpoint.close();
    assert.throws(()=>validateEditorPublication(f.snapshot,f.surface,{...publication,retirement:{...retirement,authorityRetired:false}}));
  }
});
test('pending resolver marker is exact, grants no basis and permits later checked publication',()=>{
  const f=frame(),endpoint=createBrowserEditorEndpoint({send:async()=>assert.fail('Pending metadata cannot dispatch')});
  endpoint.accept(f.snapshot,f.surface,null);
  const pending=endpoint.resolveBasis(f.snapshot,f.surface);
  assert.deepEqual(pending,{pending:true});assert(Object.isFrozen(pending));assert.deepEqual(Object.keys(pending),['pending']);
  assert.throws(()=>validateEditorOperation({type:'editorSubmit',packet:packet(f)},f.snapshot,f.surface,null),error=>error.stale===true);
  endpoint.accept(f.snapshot,f.surface,f.publication);
  assert.deepEqual(endpoint.resolveBasis(f.snapshot,f.surface),{basis:f.basis,settlement:null});
  endpoint.accept(f.snapshot,f.surface,{basis:null,settlement:null,composition:null,retirement:null});
  assert.equal(endpoint.resolveBasis(f.snapshot,f.surface),null,'Explicit empty redaction is hard unavailable');
  endpoint.close();assert.equal(endpoint.resolveBasis(f.snapshot,f.surface),null);
});
test('pending resolver marker excludes hard unavailable public editor states and real retirement',()=>{
  const changes=[f=>{f.surface.focused=false;},f=>{f.surface.active=false;},f=>{f.surface.serviceActive=true;},
    f=>{f.snapshot.closed=true;},f=>{f.surface.presentation.available=false;},f=>{f.surface.presentation.editor.editable=false;},f=>{f.surface.presentation.editor=null;},
    f=>{f.surface.presentation=null;},f=>{f.surface=null;},f=>{f.surface.capabilities.supported='8';delete f.surface.capabilities.mouseInputVersion;f.surface.presentation.required='8';}];
  for(const change of changes){
    const f=frame();change(f);const endpoint=createBrowserEditorEndpoint({send:async()=>assert.fail('No dispatch')});
    endpoint.accept(f.snapshot,f.surface,null);assert.equal(endpoint.resolveBasis(f.snapshot,f.surface),null);endpoint.close();
  }
  const f=frame(),retirement={availability:'available',identity:clone(f.basis.identity),observationRevision:wide,readbackAttested:true,authorityRetired:true};
  const publication={basis:null,settlement:null,composition:null,retirement},endpoint=createBrowserEditorEndpoint({send:async()=>assert.fail('No dispatch')});
  endpoint.accept(f.snapshot,f.surface,publication);
  assert.deepEqual(endpoint.resolveBasis(f.snapshot,f.surface),{basis:null,settlement:null,retirement});endpoint.close();
});
test('ended null completion keeps actual ended transaction paired before its receipt resolves',async()=>{
  const initial=frame();initial.basis.composition=initial.surface.presentation.editor.compositionTransaction='23';
  initial.surface.composition='23';initial.publication={basis:clone(initial.basis),settlement:null,composition:{transaction:'23',state:'live'},retirement:null};
  const p=packet(initial);p.observation={...p.observation,kind:'composition',authority:'composition',group:null,transaction:'23',data:{operation:'cancel',text:'',selection:[0,0]}};
  const next=frame();next.surface.presentation=null;
  const retirement={availability:'available',identity:clone(initial.basis.identity),observationRevision:wide,readbackAttested:true,authorityRetired:true};
  const r={...receipt(p),basis:null,continuity:'replaced',composition:{transaction:'23',state:'ended'},retirement};
  next.publication={basis:null,settlement:{session:r.session,id:r.id,predecessor:r.predecessor,submittedToken:r.submittedToken},composition:clone(r.composition),retirement:clone(retirement)};
  let endpoint,sequence=0;
  endpoint=createBrowserEditorEndpoint({send:async operation=>{
    const reply={type:operation.type,sequence:String(++sequence),ticket:'17'};
    if(operation.type==='editorTake'){
      reply.completion={ticket:'17',admission:'completed',receipt:r,detail:''};
      endpoint.accept(next.snapshot,next.surface,next.publication,reply);
    }else endpoint.accept(initial.snapshot,initial.surface,initial.publication,reply);
    return reply;
  }});
  endpoint.accept(initial.snapshot,initial.surface,initial.publication);
  assert.deepEqual(await endpoint.sendObservation(p),r);
  assert.deepEqual(endpoint.resolveBasis(next.snapshot,next.surface),{basis:null,settlement:next.publication.settlement,retirement});
  endpoint.close();
  for(const composition of [null,{transaction:'24',state:'ended'}]){
    const checked=createBrowserEditorEndpoint({send:async()=>assert.fail('No dispatch')});
    assert.throws(()=>checked.accept(next.snapshot,next.surface,{...next.publication,composition},{type:'editorTake',sequence:'2',ticket:'17',completion:{ticket:'17',admission:'completed',receipt:r,detail:''}}),/paired publication/);
    checked.close();
  }
  assert.throws(()=>validateEditorPublication(next.snapshot,next.surface,{...next.publication,composition:{transaction:'23',state:'live'}}));
  assert.throws(()=>validateEditorPublication(next.snapshot,next.surface,{...next.publication,retirement:null}));
  assert.throws(()=>validateEditorPublication(initial.snapshot,initial.surface,next.publication),'Actual ended proof cannot pair with a public live composition');
});
test('old renderer profiles do not delegate editor operations',()=>{
  const f=frame();assert.throws(()=>validateEditorOperation({type:'editorSubmit',packet:packet(f)},f.snapshot,{...f.surface,version:1},f.publication));
});
test('actual Client and MessageChannel accept paired metadata before resolving editor replies',async()=>{
  const ports=new MessageChannel(),generation='editor-channel',frames=[],sent=[],failures=[];
  let hostChannel,endpoint,current=frame();const p=packet(current),next=frame('9007199254741003','9007199254741004',[2,2]),r=receipt(p,next);
  const state=(ack,reply=null)=>({epoch:'fixture',ack:String(ack),snapshot:current.snapshot,surface:current.surface,editor:current.publication,editorReply:reply,service:null,error:''});
  const client=new Client(async envelope=>{
    sent.push(clone(envelope));const operation=envelope.operation;
    const reply={type:operation.type,sequence:envelope.seq,...(operation.type==='editorResync'?{}:{ticket:'21'})};
    if(operation.type==='editorTake'){
      current=next;current.publication={basis:clone(next.basis),settlement:{session:r.session,id:r.id,predecessor:r.predecessor,submittedToken:r.submittedToken},composition:null,retirement:null};
      reply.completion={ticket:'21',admission:'completed',receipt:r,detail:''};
    }
    return state(envelope.seq,reply);
  },value=>hostChannel?.accept(value));
  client.accept(state(0));
  hostChannel=createHostChannel({port:ports.port1,generation,client,surfaceProtocol,editorProtocol:protocol,onFailure:e=>failures.push(e),onBound:()=>hostChannel.accept(client.state)});
  const requests=createRendererRequests({port:ports.port2,generation,surfaceProtocol,editorProtocol:protocol,acceptSnapshot:(snapshot,_,surface,hasSurface,editor,reply)=>{assert(hasSurface);frames.push(reply);endpoint.accept(snapshot,surface,editor,reply);},present(){},onFailure:e=>failures.push(e)});
  endpoint=createBrowserEditorEndpoint({send:operation=>requests.send(operation)});
  for(let n=0;n<8;++n)await new Promise(resolve=>setImmediate(resolve));
  await endpoint.resync();assert.equal(sent[0].operation.type,'editorResync');assert.equal(frames.at(-1).sequence,sent[0].seq);
  const completed=await endpoint.sendObservation(p);assert.deepEqual(completed,r);
  assert.equal(frames.at(-1).completion.receipt.submittedToken,p.basis.token);
  assert.deepEqual(endpoint.resolveBasis(current.snapshot,current.surface),{basis:next.basis,settlement:current.publication.settlement});
  assert.deepEqual(sent.map(value=>value.operation.type),['editorResync','editorSubmit','editorTake']);
  assert.equal(failures.length,0);
  endpoint.close();requests.close();hostChannel.close();client.close();
});
test('a known receipt cannot be exposed with a different accepted owner projection',()=>{
  const f=frame(),p=packet(f),r=receipt(p),endpoint=createBrowserEditorEndpoint({send:async()=>assert.fail('No operation')});
  const publication={...f.publication,settlement:{session:r.session,id:r.id,predecessor:r.predecessor,submittedToken:r.submittedToken}};
  assert.throws(()=>endpoint.accept(f.snapshot,f.surface,publication,{type:'editorTake',sequence:'2',ticket:'17',completion:{ticket:'17',admission:'completed',receipt:r,detail:''}}),/paired publication/);
  endpoint.close();
});
test('a malformed editor result rejects its current pending promise before channel closure',async()=>{
  const sent=[],failures=[],port={postMessage:value=>sent.push(value),start(){},close(){}};
  const requests=createRendererRequests({port,generation:'fixture',surfaceProtocol,editorProtocol:protocol,acceptSnapshot(){},present(){},onFailure:error=>failures.push(error)});
  const pending=requests.send({type:'editorTake',ticket:'17'});let settled=false;
  pending.catch(()=>{settled=true;});const request=sent.at(-1);
  port.onmessage({data:{protocol:'foundation-renderer-v1',type:'result',generation:'fixture',id:request.id,ok:true,error:'',reply:{type:'editorTake',sequence:'1',ticket:'18',completion:null}},ports:[]});
  await new Promise(resolve=>setImmediate(resolve));assert.equal(settled,true,'Invalid editor metadata must not strand the removed pending request');
  await assert.rejects(pending,/ticket differs/);assert.equal(failures.length,1);requests.close();
});
