import assert from 'node:assert/strict';
import {MessageChannel} from 'node:worker_threads';
import {pathToFileURL} from 'node:url';
import {readFile} from 'node:fs/promises';
const {clonePacket,validateRendererOperation,publicSnapshot,createHostChannel,createRendererRequests} = await import(pathToFileURL(process.argv[2]));
const {Client,MAX_OPERATION_BYTES} = await import(pathToFileURL(process.argv[3]));
// Existing binary HTML prefixes use the original fixed module graph. Optional
// rich protocol injection must not add imports or exports to this shared node.
const channelSource=await readFile(pathToFileURL(process.argv[2]),'utf8');
assert.deepEqual([...channelSource.matchAll(/import\s*\{[^}]*\}\s*from\s*['"]([^'"]+)['"]/g)].map(value=>value[1]),['./browser_limits.mjs']);
assert.deepEqual([...channelSource.matchAll(/export\s+(?:function|class|const)\s+([A-Za-z_$][\w$]*)/g)].map(value=>value[1]).sort(),
  ['clonePacket','validateRendererOperation','publicSnapshot','createHostChannel','createRendererRequests'].sort());
assert(!/\bimport\s*\(/.test(channelSource),'Legacy channel acquired a dynamic dependency');
const protocol='foundation-renderer-v1',generation='test-generation';
const flush=async()=>{for(let n=0;n<8;++n)await new Promise(resolve=>setImmediate(resolve));};
const key={id:'editor',generation:'1'};
const widget={key,kind:5,text:'old',visible:true,enabled:true,inModal:true,readOnly:false,submit:1,options:[],actions:[],records:[]};
const snapshot=text=>({revision:'1',title:'Fixture',palette:{},width:100,height:100,scale:1,pages:[],activePage:null,widgets:[{...widget,text}],measurements:[{id:'1',request:{text:'measure'}}],keyBindings:[],focus:null,popup:null,closed:false});
const state=(ack,text='old')=>({epoch:'test',ack:String(ack),snapshot:snapshot(text),service:null,error:''});
const sched=()=>{let next=0;const timers=new Map();return {timers,setTimeout(run){timers.set(++next,run);return next;},clearTimeout(id){timers.delete(id);}};};
assert.throws(()=>clonePacket(new Array(100000000)),/structure|Sparse/);
assert.throws(()=>clonePacket(new Array(3)),/Sparse/);
assert.throws(()=>clonePacket({text:'x'.repeat(MAX_OPERATION_BYTES+1)}),/byte limit/);
assert.throws(()=>clonePacket({number:Infinity}),/unsupported/);
assert.throws(()=>validateRendererOperation({type:'service',id:'7'},snapshot('old')),/not delegated/);
assert.throws(()=>validateRendererOperation({type:'editIntent',key,value:'new',base:'forged'},snapshot('old')),/shape/);
assert.throws(()=>validateRendererOperation({type:'measure',values:[{id:'1',width:NaN,height:1}]},snapshot('old')),/measurement/);
assert.throws(()=>validateRendererOperation({type:'measure',values:[{id:'99',width:1,height:1}]},snapshot('old')),error=>error.stale);
assert.throws(()=>validateRendererOperation({type:'editIntent',key:{...key,generation:'2'},value:'new'},snapshot('old')),error=>error.stale);
assert.doesNotThrow(()=>validateRendererOperation({type:'selection',key,anchor:'0',caret:'1'},{...snapshot('old'),widgets:[{...widget,readOnly:true}]}));
assert.doesNotThrow(()=>validateRendererOperation({type:'pointer',key,kind:'press',pointerId:'1',x:0,y:0,wheelX:0,wheelY:0,control:false,shift:false,alt:false},{...snapshot('old'),widgets:[{...widget,pointerInput:true}]}));
const context={type:'pointer',key,kind:'context',pointerId:'0',x:20,y:10,wheelX:0,wheelY:0,control:false,shift:false,alt:false};
const contextSnapshot={...snapshot('old'),widgets:[{...widget,contextInput:true,pointerInput:false}]};
assert.doesNotThrow(()=>validateRendererOperation(context,contextSnapshot));
assert.throws(()=>validateRendererOperation(context,snapshot('old')),error=>error.stale);
assert.throws(()=>validateRendererOperation(context,{...snapshot('old'),widgets:[{...widget,pointerInput:true}]}),error=>error.stale);
for(const values of [{pointerId:'1'},{wheelX:1},{wheelY:-1}])
  assert.throws(()=>validateRendererOperation({...context,...values},contextSnapshot),/pointer/);
for(const values of [{visible:false},{enabled:false},{inModal:false},{key:{...key,generation:'2'}}])
  assert.throws(()=>validateRendererOperation(context,{...contextSnapshot,widgets:[{...contextSnapshot.widgets[0],...values}]}),error=>error.stale);
assert.throws(()=>validateRendererOperation({...context,kind:'press',pointerId:'1'},contextSnapshot),error=>error.stale);
assert.throws(()=>validateRendererOperation(context,{...contextSnapshot,popup:{key}}),error=>error.stale);
assert.deepEqual(publicSnapshot({...snapshot('old'),service:{token:'secret'},epoch:'secret',ack:'4'}),snapshot('old'));
for(const appearance of [{},{textFrame:true},{textFrame:false}]) {
  const view={...snapshot('old'),widgets:[{...widget,...appearance}]};
  assert.deepEqual(publicSnapshot(view),view,'text framing must cross the public widget records without changing the default');
  assert.throws(()=>validateRendererOperation({type:'editIntent',key,value:'new',textFrame:false},view),/shape/,
    'renderer input must not forge an authoritative appearance change');
}
const commandKey={id:'command.undo',generation:'9007199254740993'};
const command={key:commandKey,enabled:false,scope:key};
const shortcut=(code=14,shift=false)=>({type:'shortcut',key:code,control:true,shift,alt:false});
const commandSnapshot={...snapshot('old'),commands:[command],keyBindings:[
  {key:14,target:commandKey,control:true,shift:false,alt:false,focus:key},
  {key:14,target:commandKey,control:true,shift:true,alt:false,focus:key},
  {key:15,target:commandKey,control:true,shift:false,alt:false,focus:key}]};
assert.deepEqual(publicSnapshot({...commandSnapshot,service:{token:'secret'},epoch:'secret',ack:'4'}),commandSnapshot,
  'command metadata must cross the isolated channel without host-private state or numeric generation conversion');
for(const operation of [shortcut(),shortcut(14,true),shortcut(15)])
  assert.doesNotThrow(()=>validateRendererOperation(operation,commandSnapshot),'declared Ctrl+Z/Shift+Z/Y must remain delegated when disabled');
assert.throws(()=>validateRendererOperation(shortcut(16),commandSnapshot),/shortcut/);
assert.throws(()=>validateRendererOperation({...shortcut(),source:key},commandSnapshot),/shape/);
assert.throws(()=>validateRendererOperation({...shortcut(),target:commandKey},commandSnapshot),/shape/);
assert.throws(()=>validateRendererOperation({type:'activate',key:commandKey},commandSnapshot),error=>error.stale,
  'a command identity must not gain a direct widget capability');
assert.throws(()=>validateRendererOperation(shortcut(),{...commandSnapshot,keyBindings:[]}),error=>error.stale);
// A queued check runs only at first preparation and has no sequence side effect.
{
  let current=true,checks=0;const sent=[];
  const client=new Client(async envelope=>{sent.push(envelope);return state(envelope.seq);},()=>{});
  client.failed=true;client.accept(state(0));
  const rejected=client.send({type:'poll'},null,()=>{++checks;if(!current)throw Error('obsolete');}).catch(error=>error);
  current=false;client.retry();assert.match((await rejected).message,/obsolete/);assert.equal(client.ack,0n);assert.equal(sent.length,0);assert.equal(checks,1);
  let fail=true;
  client.exchange=async envelope=>{sent.push(JSON.stringify(envelope));if(fail)throw Error('uncertain');return state(envelope.seq);};
  const result=client.send({type:'poll'},null,()=>{++checks;});await flush();assert(client.failed);
  current=false;fail=false;client.retry();await result;assert.equal(checks,2);assert.equal(sent[0],sent[1]);client.close();
}
{
  let client;
  client=new Client(async envelope=>state(envelope.seq),accepted=>{if(accepted.ack==='1')client.close();});
  client.accept(state(0));await assert.rejects(client.send({type:'poll'}),/closed/);assert.equal(client.queuedBytes,0);
}
// State acknowledgments precede completions, while only one state is in flight.
{
  const ports=new MessageChannel(),scheduler=sched(),accepted=[],presented=[],failures=[],sent=[];
  let hostChannel;
  const client=new Client(async envelope=>{sent.push(envelope);return state(envelope.seq,envelope.operation.value ?? 'updated');},value=>hostChannel?.accept(value));
  client.accept(state(0));
  hostChannel=createHostChannel({port:ports.port1,generation,client,scheduler,onBound:()=>hostChannel.accept(client.state),onFailure:error=>failures.push(error)});
  const renderer=createRendererRequests({port:ports.port2,generation,acceptSnapshot:value=>accepted.push(value),present:value=>presented.push(value),onFailure:error=>failures.push(error)});
  await flush();
  const edit=renderer.send({type:'editIntent',key,value:'new'});
  await edit;assert.equal(accepted.at(-1).widgets[0].text,'new');assert.equal(sent[0].operation.base,'old');assert.equal(sent[0].operation.type,'edit');
  await assert.rejects(renderer.send({type:'editIntent',key:{...key,generation:'2'},value:'stale'}),/available/);
  assert.equal(sent.length,1);assert.equal(failures.length,0);
  client.state=state(2,'authoritative');hostChannel.accept(client.state);await flush();
  hostChannel.close();renderer.close();client.close();assert.equal(scheduler.timers.size,0);
}
// DOM focus reaches the host asynchronously. A following scoped command must
// queue behind that focus acknowledgment rather than reject against old focus.
{
  const secondKey={id:'second',generation:'1'};
  const view={...commandSnapshot,commands:[{...command,enabled:true,scope:secondKey}],
    widgets:[widget,{...widget,key:secondKey}],focus:key,
    keyBindings:[{...commandSnapshot.keyBindings[0],focus:secondKey}]};
  const current=(ack,focus=key)=>({...state(ack),snapshot:{...view,focus}});
  const ports=new MessageChannel(),scheduler=sched(),sent=[],accepted=[],failures=[];let finishFocus,hostChannel;
  const client=new Client(envelope=>{
    sent.push(envelope);
    if(envelope.operation.type==='focus')return new Promise(resolve=>{finishFocus=()=>resolve(current(envelope.seq,secondKey));});
    assert.deepEqual(client.state.snapshot.focus,secondKey,'command preparation must follow the preceding focus acknowledgment');
    return Promise.resolve(current(envelope.seq,secondKey));
  },value=>hostChannel?.accept(value));
  client.accept(current(0));
  hostChannel=createHostChannel({port:ports.port1,generation,client,scheduler,onBound:()=>hostChannel.accept(client.state),onFailure:error=>failures.push(error)});
  const renderer=createRendererRequests({port:ports.port2,generation,acceptSnapshot:value=>accepted.push(value),present(){},onFailure:error=>failures.push(error)});
  await flush();
  const focus=renderer.send({type:'focus',key:secondKey});await flush();
  const activation=renderer.send(shortcut());await flush();
  assert.equal(sent.length,1);assert.deepEqual(client.state.snapshot.focus,key);
  finishFocus();await Promise.all([focus,activation]);
  assert.equal(sent.length,2);assert.deepEqual(sent[1].operation,shortcut());
  assert.deepEqual(accepted.at(-1).commands,view.commands);assert.equal(failures.length,0);
  hostChannel.close();renderer.close();client.close();assert.equal(scheduler.timers.size,0);
}
// A queued declaration replaced before dispatch is rejected without an exchange
// or sequence increment, while its initial receipt still had a valid stroke.
{
  const ports=new MessageChannel(),scheduler=sched(),sent=[],failures=[];let hostChannel;
  const client=new Client(async envelope=>{sent.push(envelope);return state(envelope.seq);},value=>hostChannel?.accept(value));
  client.accept({...state(0),snapshot:commandSnapshot});client.failed=true;
  hostChannel=createHostChannel({port:ports.port1,generation,client,scheduler,onBound:()=>hostChannel.accept(client.state),onFailure:error=>failures.push(error)});
  const renderer=createRendererRequests({port:ports.port2,generation,acceptSnapshot(){},present(){},onFailure:error=>failures.push(error)});
  await flush();const activation=renderer.send(shortcut()).catch(error=>error);await flush();
  client.state={...client.state,snapshot:{...commandSnapshot,commands:[],keyBindings:[]}};client.retry();
  assert.match((await activation).message,/Shortcut is no longer available/);assert.equal(sent.length,0);assert.equal(client.ack,0n);assert.equal(failures.length,0);
  hostChannel.close();renderer.close();client.close();assert.equal(scheduler.timers.size,0);
}
// A host dialog can finish while its ordered completion is still in flight.
// Input queued behind that completion validates service eligibility at dispatch.
{
  const ports=new MessageChannel(),scheduler=sched(),sent=[];let finishService,hostChannel;
  const client=new Client(envelope=>{
    sent.push(envelope);
    if(envelope.operation.type==='service')return new Promise(resolve=>{finishService=()=>resolve(state(envelope.seq,'after service'));});
    return Promise.resolve(state(envelope.seq,envelope.operation.value));
  },value=>hostChannel?.accept(value));
  client.accept({...state(0),service:{id:'7',kind:2}});
  hostChannel=createHostChannel({port:ports.port1,generation,client,scheduler,onBound:()=>hostChannel.accept(client.state),onFailure:error=>assert.fail(error.message)});
  const renderer=createRendererRequests({port:ports.port2,generation,acceptSnapshot(){},present(){},onFailure:error=>assert.fail(error.message)});
  await flush();
  const completion=client.send({type:'service',id:'7',status:'cancelled',value:'',error:''});
  const edit=renderer.send({type:'editIntent',key,value:'after dialog'});
  await flush();assert.equal(sent.length,1);finishService();await Promise.all([completion,edit]);
  assert.equal(sent[1].operation.type,'edit');assert.equal(sent[1].operation.base,'after service');
  hostChannel.close();renderer.close();client.close();
}
{
  const ports=new MessageChannel(),scheduler=sched();let hostChannel;
  const client=new Client(async()=>assert.fail('Input dispatched while host service remains active'),value=>hostChannel?.accept(value));
  client.accept({...state(0),service:{id:'7',kind:2}});
  hostChannel=createHostChannel({port:ports.port1,generation,client,scheduler,onBound:()=>hostChannel.accept(client.state),onFailure:error=>assert.fail(error.message)});
  const renderer=createRendererRequests({port:ports.port2,generation,acceptSnapshot(){},present(){},onFailure:error=>assert.fail(error.message)});
  await flush();await assert.rejects(renderer.send({type:'editIntent',key,value:'during prompt'}),/host service is active/);assert.equal(client.ack,0n);
  hostChannel.close();renderer.close();client.close();
}
// A stalled renderer retains one packet and only the newest replacement.
{
  const ports=new MessageChannel(),scheduler=sched(),received=[],failures=[];
  const client=new Client(async()=>assert.fail('no exchange'),()=>{});client.accept(state(0));
  const channel=createHostChannel({port:ports.port1,generation,client,scheduler,onBound:()=>channel.accept(client.state),onFailure:error=>failures.push(error)});
  ports.port2.onmessage=event=>received.push(event.data);ports.port2.start();
  ports.port2.postMessage({protocol,type:'bound',generation});await flush();
  for(let n=1;n<=100;++n)channel.accept(state(n,String(n)));
  await flush();assert.equal(received.length,1,'Do not enqueue snapshots behind a stalled child');assert.equal(scheduler.timers.size,1);
  ports.port2.postMessage({protocol,type:'stateAck',generation,revision:received[0].revision});await flush();
  assert.equal(received.length,2);assert.equal(received[1].snapshot.widgets[0].text,'100');
  [...scheduler.timers.values()][0]();assert.match(failures[0].message,/acknowledge/);channel.close();ports.port2.close();client.close();
}
// Unauthorized, duplicate, wrong-generation and oversized packets fail closed.
for(const malicious of [
  {protocol,type:'request',generation,id:'1',operation:{type:'fileRead',id:'7',offset:'0'}},
  {protocol,type:'request',generation:'old',id:'1',operation:{type:'editIntent',key,value:'x'}},
  {protocol,type:'request',generation,id:'2',operation:{type:'editIntent',key,value:'x'}},
  {protocol,type:'request',generation,id:'1',operation:{type:'editIntent',key,value:'x'.repeat(MAX_OPERATION_BYTES)}}
]) {
  const ports=new MessageChannel(),scheduler=sched(),failures=[];
  const client=new Client(async()=>assert.fail('unauthorized exchange'),()=>{});client.accept(state(0));
  const channel=createHostChannel({port:ports.port1,generation,client,scheduler,onFailure:error=>failures.push(error)});
  ports.port2.postMessage({protocol,type:'bound',generation});await flush();ports.port2.postMessage(malicious);await flush();
  assert.equal(failures.length,1);assert.equal(client.ack,0n);channel.close();ports.port2.close();client.close();
}
// A trusted native owner can suspend input without a legacy dialog descriptor.
// A descriptor still requires suspension, and the injected validator owns shape.
for(const entry of [
  {service:null,active:true,reject:false},
  {service:{id:'7',kind:2},active:true,reject:false},
  {service:{id:'7',kind:2},active:false,reject:true},
  {service:null,active:1,reject:true}
]){
  const ports=new MessageChannel(),failures=[],client=new Client(async()=>assert.fail('No exchange'),()=>{});
  const surfaceProtocol={validateSurfaceState(snapshot,surface){if(typeof surface.serviceActive!=='boolean')throw Error('Invalid service suspension');},validateSurfaceOperation(){assert.fail('No operation');}};
  const channel=createHostChannel({port:ports.port1,generation,client,surfaceProtocol,onFailure:error=>failures.push(error)});
  channel.accept({...state(0),service:entry.service,surface:{serviceActive:entry.active}});
  assert.equal(failures.length,entry.reject?1:0);
  channel.close();ports.port2.close();client.close();
}
console.log('Typed current renderer intents, initial-only guards, exact retry, ordered state/completions, bounded stalled state, native service authority and protocol rejection passed');

// Document values use the same serial Client/isolated state ACK route, without
// changing the legacy channel graph or importing a feature-specific backend.
const {validateDocumentState,validateDocumentOperation,validateDocumentReply}=await import(new URL('../host/browser_document_endpoint.mjs',import.meta.url));
const documentProtocol=Object.freeze({validateDocumentState,validateDocumentOperation,validateDocumentReply});
const emptyDocument=(extra={})=>({version:1,publicationRevision:'0',available:true,phase:'idle',observation:null,draft:null,pending:null,document:null,...extra});
const documentState=(ack,extra={},reply=null)=>({...state(ack),document:emptyDocument(extra),documentReply:reply});
const documentSubmit={type:'documentSubmit',version:1,intent:{kind:'observe'}};
const documentTake={type:'documentTake',version:1,ticket:'53'};
const documentReply=(sequence,operation,completion=null)=>({sequence:String(sequence),operation,admission:'accepted',ticket:'53',completion});
assert.throws(()=>validateRendererOperation(documentSubmit,snapshot('old')),/not delegated/);
assert.deepEqual(validateRendererOperation(documentSubmit,snapshot('old'),undefined,null,null,null,documentProtocol,emptyDocument()),documentSubmit);
assert.throws(()=>validateRendererOperation({...documentSubmit,intent:{kind:'observe',nativeLease:'53'}},snapshot('old'),undefined,null,null,null,documentProtocol,emptyDocument()));
for(const create of [createHostChannel,createRendererRequests])assert.throws(()=>create({documentProtocol:{validateDocumentState}}),/document protocol/);
{
  const ports=new MessageChannel(),scheduler=sched(),accepted=[],presented=[],failures=[],sent=[];let channel;
  const client=new Client(async envelope=>{
    sent.push(envelope);const take=envelope.operation.type==='documentTake';
    return documentState(envelope.seq,take?{phase:'idle'}:{phase:'waitingTake',pending:'53'},documentReply(envelope.seq,take?'take':'submit',take?{ticket:'53',outcome:'completed',observation:null,draft:null,detail:''}:null));
  },value=>channel?.accept(value));client.accept(documentState(0));
  channel=createHostChannel({port:ports.port1,generation,client,scheduler,documentProtocol,onBound:()=>channel.accept(client.state),onFailure:error=>failures.push(error)});
  const renderer=createRendererRequests({port:ports.port2,generation,documentProtocol,acceptSnapshot(...args){accepted.push(args);},present(value){presented.push(value);},onFailure:error=>failures.push(error)});
  await flush();const submitReply=await renderer.send(documentSubmit);
  assert.equal(submitReply.sequence,'1');assert.equal(accepted.at(-1)[6].phase,'waitingTake');assert.equal(accepted.at(-1)[7].sequence,'1');assert.equal(accepted.at(-1)[3],false,'A document-only capability must not invent a physical surface');
  const completion=await renderer.send(documentTake);assert.equal(completion.completion.outcome,'completed');assert.equal(accepted.at(-1)[6].pending,null);assert.equal(accepted.at(-1)[7].sequence,'2');assert.equal(presented.length,3);assert.equal(sent.length,2);assert.equal(failures.length,0);
  channel.close();renderer.close();client.close();assert.equal(scheduler.timers.size,0);
}
// Every paired document metadata state is retained in order while a child is
// stalled, even when no editor protocol is present. Existing bounds still apply.
{
  const ports=new MessageChannel(),scheduler=sched(),received=[],failures=[];const client=new Client(async()=>assert.fail('No exchange'),()=>{});client.accept(documentState(0));
  const channel=createHostChannel({port:ports.port1,generation,client,scheduler,documentProtocol,onBound:()=>channel.accept(client.state),onFailure:error=>failures.push(error)});
  ports.port2.onmessage=event=>received.push(event.data);ports.port2.start();ports.port2.postMessage({protocol,type:'bound',generation});await flush();
  for(const phase of ['queued','waitingAck','waitingTake'])channel.accept(documentState(0,{phase,pending:'53'}));
  assert.equal(received.length,1);
  for(let n=0;n<3;++n){ports.port2.postMessage({protocol,type:'stateAck',generation,revision:received.at(-1).revision});await flush();assert.equal(received.at(-1).document.phase,['queued','waitingAck','waitingTake'][n]);}
  assert.equal(received.length,4);assert.equal(failures.length,0);channel.close();ports.port2.close();client.close();assert.equal(scheduler.timers.size,0);
}
// A modal service permits local Take metadata, while ordinary Submit remains
// subject to the same service-ownership guard as other application input.
{
  const ports=new MessageChannel(),scheduler=sched(),sent=[],failures=[];let channel;
  const current=(ack,reply=null)=>({...documentState(ack,{pending:'53',phase:'waitingAck'},reply),service:{id:'7',kind:2}});
  const client=new Client(async envelope=>{sent.push(envelope);return current(envelope.seq,documentReply(envelope.seq,'take'));},value=>channel?.accept(value));client.accept(current(0));
  channel=createHostChannel({port:ports.port1,generation,client,scheduler,documentProtocol,onBound:()=>channel.accept(client.state),onFailure:error=>failures.push(error)});
  const renderer=createRendererRequests({port:ports.port2,generation,documentProtocol,acceptSnapshot(){},present(){},onFailure:error=>failures.push(error)});
  await flush();await assert.rejects(renderer.send(documentSubmit),/host service is active/);assert.equal(sent.length,0);assert.equal(client.ack,0n);
  assert.equal((await renderer.send(documentTake)).sequence,'1');assert.equal(sent.length,1);assert.equal(failures.length,0);channel.close();renderer.close();client.close();
}
for(const invalidState of [
  {...documentState(0),document:emptyDocument({publicationRevision:'2'})},
  {...documentState(0),documentReply:{...documentReply('1','submit'),nativeAck:true}},
  (()=>{const value=documentState(0);delete value.documentReply;return value;})()
]){
  const ports=new MessageChannel(),failures=[],client=new Client(async()=>assert.fail('No exchange'),()=>{});client.accept(documentState(0));
  const channel=createHostChannel({port:ports.port1,generation,client,documentProtocol,onFailure:error=>failures.push(error)});channel.accept(invalidState);assert.equal(failures.length,1);channel.close();ports.port2.close();client.close();
}
// The child validates the paired values before its acceptance/paint callbacks.
{
  const ports=new MessageChannel(),failures=[];let callbacks=0;ports.port1.onmessage=()=>{};ports.port1.start();
  const renderer=createRendererRequests({port:ports.port2,generation,documentProtocol,acceptSnapshot(){++callbacks;},present(){++callbacks;},onFailure:error=>failures.push(error)});
  ports.port1.postMessage({protocol,type:'state',generation,revision:'1',snapshot:snapshot('old'),barrier:true,cancelPointers:false,document:emptyDocument({publicationRevision:'2'}),documentReply:null});await flush();assert.equal(callbacks,0);assert.equal(failures.length,1);renderer.close();ports.port1.close();
}
// A crossed GUI acknowledgment cannot resolve a typed document request.
{
  const ports=new MessageChannel(),scheduler=sched(),failures=[];let channel;
  const client=new Client(async envelope=>documentState(envelope.seq,{pending:'53'},documentReply('99','submit')),value=>channel?.accept(value));client.accept(documentState(0));
  channel=createHostChannel({port:ports.port1,generation,client,scheduler,documentProtocol,onBound:()=>channel.accept(client.state),onFailure:error=>failures.push(error)});
  const renderer=createRendererRequests({port:ports.port2,generation,documentProtocol,acceptSnapshot(){},present(){}});await flush();const pending=renderer.send(documentSubmit).catch(error=>error);await flush();assert.equal(failures.length,1);renderer.close();assert.match((await pending).message,/closed/);channel.close();client.close();assert.equal(scheduler.timers.size,0);
}
console.log('Optional document delegation, ordered paired states, original GUI acknowledgment correlation, service metadata Take, strict child validation and legacy graph preservation passed');
