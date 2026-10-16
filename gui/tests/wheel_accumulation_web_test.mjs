import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {resolve} from 'node:path';
const load=argument=>import(pathToFileURL(resolve(argument)));
const {Renderer,identity}=await load(process.argv[2]);
const {Client,MAX_OPERATION_BYTES,MAX_QUEUED_BYTES}=await load(process.argv[3]);
const {createHostChannel,createRendererRequests,validateRendererOperation}=await load(process.argv[4]);
const copy=value=>JSON.parse(JSON.stringify(value));
const turn=()=>new Promise(resolve=>setImmediate(resolve));
const key=(id,generation='1')=>({id,generation});
const group=(id='outer',parent='',values={})=>({key:key(id),kind:0,parent,visible:true,enabled:true,inModal:true,
  bounds:[0,0,100,100],contentSize:[100,500],scroll:[0,50],...values});
const snapshot=widgets=>({revision:'1',width:100,height:100,scale:1,widgets,pages:[],measurements:[],keyBindings:[],commands:[],closed:false});
class Element {
  constructor(){this.events=new Map();this.style={};this.dataset={};}
  addEventListener(kind,callback){this.events.set(kind,callback);}
  removeEventListener(kind){this.events.delete(kind);}
}
function ports(){
  const pair=[0,1].map(()=>({closed:false,start(){},close(){this.closed=true;this.onmessage=null;}}));
  for(let index=0;index<2;++index)pair[index].postMessage=data=>{
    const copied=copy(data);queueMicrotask(()=>{const peer=pair[1-index];if(!peer.closed)peer.onmessage?.({data:copied});});
  };
  return pair;
}
async function fixture(widgets=[group()],isolated=false){
  let renderer,hostChannel,requests;
  const pending=[],sent=[],failures=[],statuses=[];
  let backend={epoch:'wheel-session',ack:'0',snapshot:snapshot(copy(widgets)),service:null,error:''};
  const client=new Client(envelope=>new Promise((resolve,reject)=>{
    const copied=copy(envelope);sent.push(copied);pending.push({envelope:copied,resolve,reject});
  }),state=>{if(hostChannel)hostChannel.accept(state);else renderer.acceptSnapshot(state.snapshot);},message=>statuses.push(message));
  let send=(operation,coalesce)=>client.send(operation,coalesce);
  if(isolated){
    const [host,child]=ports();
    hostChannel=createHostChannel({port:host,generation:'wheel-channel',client,onFailure:error=>failures.push(error)});
    requests=createRendererRequests({port:child,generation:'wheel-channel',
      acceptSnapshot:state=>renderer.acceptSnapshot(state),present(){},onFailure:error=>failures.push(error)});
    send=operation=>requests.send(operation);
  }
  const document={addEventListener(){},removeEventListener(){},defaultView:new Element()};
  renderer=new Renderer(new Element(),new Element(),send,document);
  renderer.snapshot=copy(backend.snapshot); // Intentionally leave visual painting delayed.
  for(const widget of widgets){const node={dataset:{key:identity(widget.key)}};renderer.nodes.set(identity(widget.key),{node,widget:copy(widget),control:node});}
  client.accept(copy(backend));await turn();
  const wheel=(id='outer',x=0,y=40)=>{
    const entry=[...renderer.nodes.values()].find(value=>value.widget.key.id===id);
    const event={target:{closest:selector=>selector==='.widget'?entry?.node:null},deltaX:x,deltaY:y,
      defaultPrevented:false,preventDefault(){this.defaultPrevented=true;}};
    renderer.groupWheel(event);return event;
  };
  const commit=(request,change)=>{
    const {envelope}=request;
    // The fake backend is independently idempotent by epoch/sequence.
    if(BigInt(envelope.seq)>BigInt(backend.ack)){
      assert.equal(envelope.seq,String(BigInt(backend.ack)+1n));
      const operation=envelope.operation;
      if(operation.type==='scroll'){
        const widget=backend.snapshot.widgets.find(value=>identity(value.key)===identity(operation.key));
        assert.ok(widget,'only an exact live group may reach the backend');widget.scroll=[operation.x,operation.y];
      }else if(operation.type==='activate')backend.snapshot.widgets.find(value=>value.kind===0).scroll=[0,0];
      else assert.fail(`unexpected backend operation ${operation.type}`);
      backend.ack=envelope.seq;backend.snapshot.revision=String(BigInt(backend.snapshot.revision)+1n);
      change?.(backend);
    }
    return copy(backend);
  };
  const finish=async(change)=>{assert.ok(pending.length,'a backend request must be outstanding');const request=pending.shift();request.resolve(commit(request,change));await turn();};
  const lose=async()=>{const request=pending.shift();assert.ok(request);commit(request);request.reject(Error('reply was lost'));await turn();};
  const drain=async()=>{for(let count=0;count<300;++count){await turn();if(pending.length){await finish();continue;}if(!client.running&&!client.queue.length&&!client.inflight)return;}assert.fail('wheel queue did not settle');};
  const scroll=(id='outer')=>backend.snapshot.widgets.find(value=>value.key.id===id).scroll;
  const close=()=>{renderer.destroy();requests?.close();hostChannel?.close();client.close();};
  return {renderer,client,send,wheel,finish,lose,drain,scroll,sent,pending,failures,statuses,close,get backend(){return backend;}};
}
for(const isolated of [false,true]){
  let f=await fixture(undefined,isolated);
  for(let index=0;index<3;++index)assert.equal(f.wheel().defaultPrevented,true);
  await f.drain();assert.equal(f.scroll()[1],170,'three delayed +40 strokes from 50 must accumulate to 170');
  assert.deepEqual(f.sent.map(value=>value.operation.y),[90,130,170]);assert.equal(f.renderer.wheelPending.count,0);f.close();

  f=await fixture([group('outer','',{contentSize:[100,5100]})],isolated);
  for(let index=0;index<20;++index)f.wheel();await f.drain();assert.equal(f.scroll()[1],850,
    'ordinary small delayed bursts must retain more than eight strokes');assert.equal(f.sent.length,20);f.close();

  f=await fixture([group('outer','',{scroll:[0,350]})],isolated);
  f.wheel('outer',0,100);f.wheel('outer',0,-100);await f.drain();assert.equal(f.scroll()[1],300,'clamp then reverse must preserve both strokes');f.close();

  f=await fixture([group(),{key:key('reset'),kind:2,visible:true,enabled:true,inModal:true}],isolated);
  f.wheel();const action=f.send({type:'activate',key:key('reset')});f.wheel();await f.drain();await action;
  assert.equal(f.scroll()[1],40,'later wheel prepares after the intervening action');
  assert.deepEqual(f.sent.map(value=>value.operation.type),['scroll','activate','scroll']);f.close();

  f=await fixture(undefined,isolated);f.wheel();const drag=f.send({type:'scroll',key:key('outer'),x:0,y:200},'scroll:outer');f.wheel();
  await f.drain();await drag;assert.equal(f.scroll()[1],240,'native absolute scrolling remains an ordering barrier');f.close();

  f=await fixture([group('outer','',{scroll:[0,0]}),group('inner','outer',{contentSize:[100,250],scroll:[0,150]})],isolated);
  f.wheel('inner');assert.equal(f.wheel('outer',0,-40).defaultPrevented,true,'pending ancestor movement must retain an immediate reversal');
  await f.drain();assert.equal(f.scroll('outer')[1],0);assert.deepEqual(f.sent.map(value=>value.operation.key.id),['outer','outer']);f.close();

  f=await fixture(undefined,isolated);f.wheel();await turn();await f.finish();
  assert.equal(f.renderer.snapshot.widgets[0].scroll[1],50,'paint remains deliberately old');f.wheel();await f.drain();assert.equal(f.scroll()[1],130);f.close();

  f=await fixture(undefined,isolated);f.wheel();f.wheel();await turn();await f.finish(state=>{
    state.snapshot.widgets[0].contentSize=[100,120];state.snapshot.widgets[0].scroll=[0,20];
  });await f.drain();assert.equal(f.sent.length,1,'geometry-clamped no-op must not consume a sequence');assert.equal(f.scroll()[1],20);f.close();

  f=await fixture(undefined,isolated);f.wheel();f.wheel();await turn();await f.finish(state=>{state.snapshot.widgets[0].key.generation='2';});
  await f.drain();assert.equal(f.sent.length,1,'queued wheel must reject a replaced generation');
  assert.equal(f.wheel().defaultPrevented,false,'old DOM identity cannot target the new generation');assert.equal(f.failures.length,0);f.close();

  for(const replacement of ['removed','closed']){
    f=await fixture(undefined,isolated);f.wheel();f.wheel();await turn();await f.finish(state=>{
      if(replacement==='removed')state.snapshot.widgets=[];else state.snapshot.closed=true;
    });await f.drain();assert.equal(f.sent.length,1,`${replacement} snapshot must reject queued wheel work`);
    assert.equal(f.wheel().defaultPrevented,false);assert.equal(f.renderer.wheelPending.count,0);assert.equal(f.failures.length,0);f.close();
  }

  f=await fixture(undefined,isolated);f.wheel();f.wheel();await turn();await f.lose();assert.equal(f.client.failed,true);
  const original=copy(f.sent[0]);f.client.retry();await f.drain();assert.deepEqual(f.sent[1],original,'retry must preserve the prepared absolute envelope exactly');
  assert.equal(f.scroll()[1],130,'lost reply must not repeat a relative effect');f.close();

  f=await fixture(undefined,isolated);f.wheel();await turn();const late=f.pending.shift();f.close();late.resolve(copy(f.backend));await turn();
  assert.equal(f.client.closed,true);assert.equal(f.client.queuedBytes,0);assert.equal(f.renderer.wheelPending.count,0);
  assert.equal(f.wheel().defaultPrevented,false);assert.equal(f.sent.length,1);
}
for(const isolated of [false,true]){
  const f=await fixture(undefined,isolated);for(let index=0;index<145;++index)f.wheel();await turn();
  assert.ok(f.client.queuedBytes<=MAX_QUEUED_BYTES);assert.ok(f.client.queue.length<=128);await f.drain();
  assert.equal(f.renderer.wheelPending.count,0);assert.equal(f.client.queuedBytes,0);assert.equal(f.scroll()[1],400);
  assert.equal(f.failures.length,0);f.wheel('outer',0,-40);await f.drain();
  assert.equal(f.scroll()[1],360,'rejected overflow must not strand earlier work or later recovery');f.close();
}

let f=await fixture();const done=[f.client.send({type:'groupWheel',key:key('outer'),x:0,y:40},'same'),
  f.client.send({type:'groupWheel',key:key('outer'),x:0,y:40},'same'),f.client.send({type:'groupWheel',key:key('outer'),x:0,y:40},'same')];
await f.drain();await Promise.all(done);assert.equal(f.scroll()[1],170,'relative intents cannot be replacement-coalesced even with an explicit key');f.close();

f=await fixture([group('outer','',{scroll:[0,400]})]);const noOp=await f.client.send({type:'groupWheel',key:key('outer'),x:0,y:40});
assert.equal(noOp.ack,'0');assert.equal(f.sent.length,0);assert.equal(f.client.queuedBytes,0);f.close();
const longIdentity='\u0001'.repeat(20000);
for(const isolated of [false,true]){
  f=await fixture([group(longIdentity,'',{scroll:[0,0]}),group('inner',longIdentity,{contentSize:[100,100],scroll:[0,0]})],isolated);
  f.wheel('inner');await turn();const wireBytes=new TextEncoder().encode(JSON.stringify(f.sent[0])).length;
  assert.ok(wireBytes>100000,'the selected ancestor must enlarge the wire envelope');
  assert.ok(f.client.queuedBytes>=wireBytes+512,'in-flight accounting must retain both intent and enlarged envelope');
  assert.ok(f.client.queuedBytes<=MAX_QUEUED_BYTES);await f.drain();assert.equal(f.scroll(longIdentity)[1],40);f.close();
}
f=await fixture([group(longIdentity,'',{scroll:[0,0]}),group('inner',longIdentity,{contentSize:[100,100],scroll:[0,0]}),
  {key:key('reset'),kind:2,visible:true,enabled:true,inModal:true}]);
f.client.failed=true;f.wheel('inner');const padding='x'.repeat(MAX_OPERATION_BYTES-2048),fillers=[];
for(let index=0;index<8;++index)fillers.push(f.client.send({type:'activate',key:key('reset'),padding}));
assert.ok(f.client.queuedBytes<=MAX_QUEUED_BYTES);f.client.retry();await f.drain();await Promise.all(fillers);
assert.equal(f.sent.filter(value=>value.operation.type==='scroll').length,0,'unaffordable envelope growth must reject before transport');
assert.equal(f.sent[0].seq,'1','local growth rejection cannot consume a sequence');assert.ok(f.statuses.some(value=>value.includes('queue is full')));
assert.equal(f.client.queuedBytes,0);f.wheel('inner');await f.drain();assert.equal(f.scroll(longIdentity)[1],40,'growth rejection must permit later recovery');f.close();
const valid=snapshot([group()]);assert.doesNotThrow(()=>validateRendererOperation({type:'groupWheel',key:key('outer'),x:-40,y:40},valid));
for(const invalid of [{x:NaN,y:0},{x:1000001,y:0},{x:0,y:0,extra:true}])assert.throws(()=>validateRendererOperation({type:'groupWheel',key:key('outer'),...invalid},valid));
assert.throws(()=>validateRendererOperation({type:'groupWheel',key:key('outer','2'),x:0,y:40},valid),error=>error.stale===true);
assert.throws(()=>validateRendererOperation({type:'groupWheel',key:key('outer'),x:0,y:40},snapshot([{...group(),kind:5}])),error=>error.stale===true);
console.log('Delayed relative wheel accumulation, clamp/reversal, barriers, accepted state, generation, bounded rejection, teardown and exact retries passed through standalone and isolated queues');
