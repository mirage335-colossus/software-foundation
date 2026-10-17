import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
import {resolve} from 'node:path';
import {runInNewContext} from 'node:vm';
import test from 'node:test';
const facadeURL=process.argv[2]?pathToFileURL(resolve(process.argv[2])):new URL('../host/appended_web_services.mjs',import.meta.url);
const {createFoundationServices,ServiceStatus:S,FoundationServiceError}=await import(facadeURL);
const HEADER=64,U64_MAX=(1n<<64n)-1n,SCHEMA=Uint8Array.from({length:32},(_,index)=>index+1);
const HANDLE=0xfedcba9876543210n,query={major:1,minMinor:0,maxMinor:3};
const view=bytes=>new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);
const hex=bytes=>Buffer.from(bytes).toString('hex');
function scalar(value,size=4) {
  const bytes=new Uint8Array(size);
  if(size===8)view(bytes).setBigUint64(0,value,true);else view(bytes).setUint32(0,value,true);
  return bytes;
}
function tlv(items) {
  const bytes=new Uint8Array(items.reduce((sum,[,,value])=>sum+8+value.length,0));let offset=0;
  for(const [id,type,value,flags=1] of items) {
    view(bytes).setUint16(offset,id,true);bytes[offset+2]=type;bytes[offset+3]=flags;
    view(bytes).setUint32(offset+4,value.length,true);bytes.set(value,offset+8);offset+=8+value.length;
  }
  return bytes;
}
const descriptorFields=({handle=HANDLE,name='fixture.echo',major=1,minor=3,schema=SCHEMA,maxReplyBytes=32}={})=>
  [[1,2,scalar(handle,8)],[2,6,new TextEncoder().encode(name)],[3,1,scalar(major)],
    [4,1,scalar(minor)],[5,7,schema],[6,1,scalar(maxReplyBytes)]];
function completion(request,{payload=new Uint8Array(),status=S.ok,change}={}) {
  const bytes=new Uint8Array(HEADER+payload.length);bytes.set(request.subarray(0,HEADER));
  const data=view(bytes);data.setUint32(0,bytes.length,true);data.setUint32(8,4,true);
  data.setUint32(44,payload.length,true);data.setUint32(48,status,true);bytes.set(payload,HEADER);
  change?.(data,bytes);return bytes;
}
const statusIs=status=>error=>error instanceof FoundationServiceError&&error.status===status;

// A fake owner/admission adapter, explicitly not an HTML engine integration.
// enqueue only retains values; pump creates results; delivery follows pump exit.
class FakeTransport {
  submissions=[];acks=[];cancels=[];effects=0;ackStatus=S.ok;enqueueStatus=S.ok;cancelStatus=S.ok;onEnqueue=null;
  enqueue(bytes,source) {
    this.submissions.push({bytes:bytes.slice(),source});
    this.onEnqueue?.(bytes,source);
    return this.enqueueStatus;
  }
  cancel(generation,sequence){this.cancels.push([generation,sequence]);return this.cancelStatus;}
  acknowledge(generation,through){this.acks.push([generation,through]);this.onAcknowledge?.();return this.ackStatus;}
  pump(index,payload=new Uint8Array()) {
    assert.equal(this.pumping,undefined);this.pumping=true;
    try {++this.effects;return completion(this.submissions[index].bytes,{payload});}
    finally{delete this.pumping;}
  }
  deliver(bytes){assert.equal(this.pumping,undefined);return this.foundation.receive(bytes);}
}
async function opened(options={},discoveryOptions=query,descriptorOptions={}) {
  const fake=new FakeTransport(),foundation=createFoundationServices(fake,{generation:1n,...options});
  fake.foundation=foundation;
  const discovery=foundation.discover('fixture.echo',discoveryOptions);
  assert.equal(fake.effects,0,'admission must not run a provider');
  assert.equal(fake.deliver(fake.pump(0,tlv(descriptorFields(descriptorOptions)))),true);
  const service=await discovery;
  assert.equal(foundation.acknowledge(),S.ok);
  return {fake,foundation,service};
}

test('fake transport reproduces the ABI golden envelope with lossless u64 values',async()=>{
  const golden=JSON.parse(await readFile(new URL('../../abi/appended/v1/golden.json',import.meta.url),'utf8')).envelope_request;
  const generation=BigInt(golden.generation),sequence=BigInt(golden.sequence),handle=BigInt(golden.interface_handle);
  const {fake,foundation,service}=await opened({generation,firstSequence:sequence-1n},query,{handle});
  const discover=fake.submissions[0];
  assert.equal(discover.source,'automatic');
  assert.equal(view(discover.bytes).getBigUint64(16,true),generation);
  assert.equal(view(discover.bytes).getBigUint64(24,true),sequence-1n);
  assert.equal(view(discover.bytes).getBigUint64(32,true),0n);
  assert.equal(view(discover.bytes).getUint32(40,true),1);
  assert.equal(hex(discover.bytes.subarray(HEADER)),hex(tlv([[1,6,new TextEncoder().encode('fixture.echo')],
    [2,1,scalar(1)],[3,1,scalar(0)],[4,1,scalar(3)]])));
  const call=service.call(Number(BigInt(golden.operation)),Uint8Array.from(Buffer.from(golden.payload_hex,'hex')));
  assert.equal(call.sequence,sequence);assert.equal(hex(fake.submissions[1].bytes),golden.hex);
  assert.equal(service.descriptor.handle,handle);
  assert.equal(fake.deliver(fake.pump(1,Uint8Array.of(0,255,128))),true);
  assert.deepEqual(await call,Uint8Array.of(0,255,128));assert.equal(foundation.acknowledge(),S.ok);
  assert.deepEqual(fake.acks.at(-1),[generation,sequence]);
});

test('discovery has an optional source while ordinary opaque-handle calls need no routing',async()=>{
  const {fake,foundation,service}=await opened({}, {...query,schema:SCHEMA,source:'module'});
  assert.equal(fake.submissions[0].source,'module');
  const publicSchema=service.descriptor.schema;publicSchema.fill(0);
  assert.deepEqual(service.descriptor.schema,SCHEMA);
  assert.equal(Object.isFrozen(service),true);assert.equal(Object.isFrozen(service.descriptor),true);
  const payload=Uint8Array.of(0,0xff,0x80),call=service.call(99,payload);payload.fill(7);
  assert.equal(fake.submissions[1].source,'automatic');
  assert.equal(view(fake.submissions[1].bytes).getBigUint64(32,true),HANDLE);
  assert.deepEqual(fake.submissions[1].bytes.subarray(HEADER),Uint8Array.of(0,255,128));
  const reply=Uint8Array.of(128,0,255),bytes=fake.pump(1,reply);
  assert.equal(fake.deliver(bytes),true);bytes.fill(0);reply.fill(0);
  assert.deepEqual(await call,Uint8Array.of(128,0,255));assert.equal(foundation.acknowledge(),S.ok);
});

test('Buffer views and hostile Uint8Array subclasses cannot alias or redefine owned values',async()=>{
  class HostileBytes extends Uint8Array {
    slice(){throw Error('virtual slice must not run');}
    subarray(){throw Error('virtual subarray must not run');}
    every(){throw Error('virtual every must not run');}
    some(){throw Error('virtual some must not run');}
    [Symbol.iterator](){throw Error('virtual iterator must not run');}
    get length(){throw Error('shadowed length must not run');}
    get byteLength(){throw Error('shadowed byteLength must not run');}
    get byteOffset(){throw Error('shadowed byteOffset must not run');}
    get buffer(){throw Error('shadowed buffer must not run');}
  }
  const conversions=[
    bytes=>{const backing=Buffer.alloc(2*1048576);backing.set(bytes,1000);return backing.subarray(1000,1000+bytes.length);},
    bytes=>{const backing=new ArrayBuffer(2*1048576),small=new HostileBytes(backing,1000,bytes.length);
      Uint8Array.prototype.set.call(small,bytes);return small;}
  ];
  for(const convert of conversions) {
    const fake=new FakeTransport(),foundation=createFoundationServices(fake,{generation:1n});fake.foundation=foundation;
    const schema=convert(SCHEMA),discovery=foundation.discover('fixture.echo',{...query,schema});
    Uint8Array.prototype.fill.call(schema,0);
    const discoveryBytes=completion(fake.submissions[0].bytes,{payload:tlv(descriptorFields())});
    const incoming=convert(discoveryBytes);
    assert.equal(fake.deliver(incoming),true);Uint8Array.prototype.fill.call(incoming,0);
    assert.equal(fake.deliver(discoveryBytes),true,'completion cache must survive mutation of the input view');
    const service=await discovery;
    const publicSchema=service.descriptor.schema;
    assert.equal(Object.getPrototypeOf(publicSchema),Uint8Array.prototype);
    assert.equal(publicSchema.buffer.byteLength,32);assert.deepEqual(publicSchema,SCHEMA);
    publicSchema.fill(0);assert.deepEqual(service.descriptor.schema,SCHEMA);
    assert.equal(foundation.acknowledge(),S.ok);
    const input=convert(Uint8Array.of(1,2,3)),call=service.call(7,input);
    Uint8Array.prototype.fill.call(input,0);
    assert.deepEqual(fake.submissions[1].bytes.subarray(HEADER),Uint8Array.of(1,2,3));
    assert.equal(fake.submissions[1].bytes.buffer.byteLength,HEADER+3);
    const resultBytes=completion(fake.submissions[1].bytes,{payload:Uint8Array.of(7,8,9)}),resultInput=convert(resultBytes);
    assert.equal(fake.deliver(resultInput),true);Uint8Array.prototype.fill.call(resultInput,0);
    const result=await call;
    assert.equal(Object.getPrototypeOf(result),Uint8Array.prototype);assert.equal(result.buffer.byteLength,3);
    assert.deepEqual(result,Uint8Array.of(7,8,9));result.fill(0);
    const replay=foundation.replay(call.sequence);assert.equal(fake.deliver(resultBytes),true);
    assert.deepEqual(await replay,Uint8Array.of(7,8,9));assert.equal(foundation.acknowledge(),S.ok);
    const oversize=convert(new Uint8Array(1048577));
    await assert.rejects(service.call(7,oversize),statusIs(S.limit_exceeded));
    assert.equal(foundation.receive(oversize),false,'intrinsic length must enforce the message limit');
  }
});

test('allocation failure before enqueue charges no slot and failed replay-copy leaves no waiter',async()=>{
  // Run the actual source in its own realm, changing only module export syntax.
  // Its constructor binding can fail selected copies without touching globals or
  // exposing a production allocation hook.
  let failCopies=0;
  const allocatingBytes=new Proxy(Uint8Array,{construct(target,args){
    if(ArrayBuffer.isView(args[0])&&failCopies>0){--failCopies;throw new RangeError('fake allocation failure');}
    return Reflect.construct(target,args);
  }});
  const source=await readFile(facadeURL,'utf8');
  const local=runInNewContext(source.replace(/^export /gm,'')+'\n;({createFoundationServices,ServiceStatus})',
    {Uint8Array:allocatingBytes,TextEncoder,TextDecoder});
  const fake=new FakeTransport(),foundation=local.createFoundationServices(fake,{generation:1n,maxRetainedCalls:1});
  fake.foundation=foundation;
  const discovery=foundation.discover('fixture.echo',query);
  assert.equal(fake.deliver(completion(fake.submissions[0].bytes,{payload:tlv(descriptorFields())})),true);
  const service=await discovery;assert.equal(foundation.acknowledge(),S.ok);
  failCopies=1;const failed=service.call(7,new Uint8Array());
  await assert.rejects(failed,error=>error.status===S.limit_exceeded);
  assert.equal(fake.submissions.length,1,'pre-admission copy failure must not call the adapter');
  assert.equal(failed.sequence,undefined);
  const call=service.call(7,new Uint8Array());assert.equal(call.sequence,2n,'failed allocation consumes no sequence or slot');
  const bytes=completion(fake.submissions[1].bytes,{payload:Uint8Array.of(9)});
  failCopies=1;assert.equal(fake.deliver(bytes),false);assert.equal(foundation.acknowledge(),S.ok);
  assert.deepEqual(fake.acks,[[1n,1n]],'failed completion copy does not ACK or settle');
  assert.equal(fake.deliver(bytes),true);assert.equal((await call)[0],9);
  failCopies=1;assert.equal(foundation.resend(call.sequence),S.limit_exceeded);
  assert.equal(fake.submissions.length,2);
  failCopies=1;const failedReplay=foundation.replay(call.sequence);
  await assert.rejects(failedReplay,error=>error.status===S.limit_exceeded);
  assert.equal(fake.submissions.length,2,'failed replay copy must not call the adapter');
  const replay=foundation.replay(call.sequence);assert.notEqual(replay,failedReplay);
  assert.equal(fake.submissions.length,3);assert.equal(fake.deliver(bytes),true);assert.equal((await replay)[0],9);
  assert.equal(foundation.acknowledge(),S.ok);
});

test('malformed and unrelated completions cannot settle or acknowledge a call',async()=>{
  const {fake,foundation,service}=await opened();const call=service.call(42,Uint8Array.of(3));
  let settled=false;call.then(()=>{settled=true;});
  const request=fake.submissions[1].bytes,good=completion(request,{payload:Uint8Array.of(4)}),acks=fake.acks.length;
  const changes=[data=>data.setUint32(0,65+1,true),data=>data.setUint16(4,2,true),data=>data.setUint16(6,1,true),
    data=>data.setUint32(8,2,true),data=>data.setUint32(12,1,true),data=>data.setBigUint64(16,2n,true),
    data=>data.setBigUint64(24,999n,true),data=>data.setBigUint64(32,HANDLE-1n,true),
    data=>data.setUint32(40,43,true),data=>data.setUint32(44,0,true),data=>data.setUint32(52,1,true),
    data=>data.setBigUint64(56,1n,true),data=>data.setUint32(48,15,true),data=>data.setUint32(48,S.result_available,true),
    data=>data.setUint32(48,S.closed,true)];
  for(const change of changes)assert.equal(fake.deliver(completion(request,{payload:Uint8Array.of(4),change})),false);
  assert.equal(fake.deliver(new Uint8Array(63)),false);
  assert.equal(fake.deliver(completion(request,{payload:new Uint8Array(33)})),false);
  await Promise.resolve();assert.equal(settled,false);
  assert.equal(foundation.acknowledge(),S.ok);assert.equal(fake.acks.length,acks);
  assert.equal(fake.deliver(good),true);assert.deepEqual(await call,Uint8Array.of(4));
  assert.equal(fake.deliver(good),true,'identical duplicate is harmless');
  const changed=good.slice();changed[HEADER]=5;assert.equal(fake.deliver(changed),false);
  assert.equal(foundation.acknowledge(),S.ok);assert.equal(fake.deliver(good),false,'retired identity cannot settle another call');
});

test('discovery validates its canonical schema and selected version before settlement',async()=>{
  const fake=new FakeTransport(),foundation=createFoundationServices(fake,{generation:1n});fake.foundation=foundation;
  const discovery=foundation.discover('fixture.echo',{...query,schema:SCHEMA});let settled=false;
  discovery.then(()=>{settled=true;});
  const request=fake.submissions[0].bytes;
  for(const bad of [{handle:0n},{name:'other.echo'},{major:2},{minor:4},{schema:new Uint8Array(32)},
    {schema:SCHEMA.subarray(1)},{maxReplyBytes:1048576}])
    assert.equal(fake.deliver(completion(request,{payload:tlv(descriptorFields(bad))})),false);
  for(const extra of [[7,7,Uint8Array.of(0),1],[7,6,Uint8Array.of(0xc0,0x80),0],
    [7,8,Uint8Array.of(1),0],[7,4,Uint8Array.from([1,0,0,0,0,0,0xf8,0x7f]),0]])
    assert.equal(fake.deliver(completion(request,{payload:tlv([...descriptorFields(),extra])})),false);
  const wrongFlags=descriptorFields();wrongFlags[0].push(0);
  assert.equal(fake.deliver(completion(request,{payload:tlv(wrongFlags)})),false);
  const duplicateId=descriptorFields();duplicateId.push([6,7,new Uint8Array(),0]);
  assert.equal(fake.deliver(completion(request,{payload:tlv(duplicateId)})),false);
  const nested=depth=>{let bytes=new Uint8Array();while(depth--)bytes=tlv([[1,8,bytes,0]]);return bytes;};
  assert.equal(fake.deliver(completion(request,{payload:tlv([...descriptorFields(),[7,8,nested(7),0]])})),false,
    'the outer record counts as depth one, so depth nine must reject');
  await Promise.resolve();assert.equal(settled,false);assert.equal(foundation.acknowledge(),S.ok);
  assert.equal(fake.acks.length,0);
  assert.equal(fake.deliver(completion(request,{payload:tlv([...descriptorFields(),
    [7,8,nested(6),0],[8,200,Uint8Array.of(9),0]])})),true,'depth eight and an unknown optional type are valid');
  assert.equal((await discovery).descriptor.minor,3);assert.equal(foundation.acknowledge(),S.ok);
});

test('explicit ACK advances only the completed prefix under out-of-order delivery',async()=>{
  const {fake,foundation,service}=await opened();const calls=[0,1,2].map(value=>service.call(8,Uint8Array.of(value)));
  assert.equal(fake.deliver(completion(fake.submissions[3].bytes)),true);await calls[2];
  assert.equal(foundation.acknowledge(),S.ok);assert.deepEqual(fake.acks,[[1n,1n]]);
  assert.equal(fake.deliver(completion(fake.submissions[1].bytes)),true);await calls[0];
  assert.equal(foundation.acknowledge(),S.ok);assert.deepEqual(fake.acks.at(-1),[1n,calls[0].sequence]);
  assert.equal(fake.deliver(completion(fake.submissions[2].bytes)),true);await calls[1];
  assert.equal(foundation.acknowledge(),S.ok);assert.deepEqual(fake.acks.at(-1),[1n,calls[2].sequence]);
});

test('retained call and byte bounds recover only after a successful ACK',async()=>{
  const {fake,foundation,service}=await opened({maxMessageBytes:512,maxRetainedCalls:2,maxRetainedBytes:1024});
  const first=service.call(1,new Uint8Array()),second=service.call(2,new Uint8Array());
  await assert.rejects(service.call(3,new Uint8Array()),statusIs(S.limit_exceeded));
  assert.equal(fake.deliver(completion(fake.submissions[2].bytes)),true);await second;
  assert.equal(foundation.acknowledge(),S.ok);
  await assert.rejects(service.call(3,new Uint8Array()),statusIs(S.limit_exceeded));
  assert.equal(fake.deliver(completion(fake.submissions[1].bytes)),true);await first;
  fake.ackStatus=S.limit_exceeded;assert.equal(foundation.acknowledge(),S.limit_exceeded);
  await assert.rejects(service.call(3,new Uint8Array()),statusIs(S.limit_exceeded));
  fake.ackStatus=S.ok;assert.equal(foundation.acknowledge(),S.ok);
  const last=service.call(3,new Uint8Array());assert.equal(fake.deliver(completion(fake.submissions[3].bytes)),true);await last;
  assert.equal(foundation.acknowledge(),S.ok);
  const tooSmall=new FakeTransport(),bounded=createFoundationServices(tooSmall,{generation:2n,maxRetainedBytes:128});
  await assert.rejects(bounded.discover('fixture.echo',query),statusIs(S.limit_exceeded));assert.equal(tooSmall.submissions.length,0);
});

test('invalid requests, shared storage, message sizes and counters fail before admission',async()=>{
  for(const generation of [1,0n,U64_MAX+1n])assert.throws(()=>createFoundationServices(new FakeTransport(),{generation}),TypeError);
  assert.throws(()=>createFoundationServices(new FakeTransport(),{generation:1n,maxMessageBytes:383}),TypeError);
  assert.doesNotThrow(()=>createFoundationServices(new FakeTransport(),{generation:1n,maxMessageBytes:384}));
  const {fake,foundation,service}=await opened({maxMessageBytes:512});const count=fake.submissions.length;
  for(const options of [{major:0,minMinor:0,maxMinor:1},{...query,minMinor:4},{...query,source:'guest'},
    {...query,schema:new Uint8Array(31)}])await assert.rejects(foundation.discover('fixture.echo',options),statusIs(S.invalid_request));
  await assert.rejects(foundation.discover('bad name',query),statusIs(S.invalid_request));
  await assert.rejects(service.call(-1,new Uint8Array()),statusIs(S.invalid_request));
  await assert.rejects(service.call(1,new ArrayBuffer(0)),statusIs(S.invalid_request));
  if(typeof SharedArrayBuffer!=='undefined') {
    await assert.rejects(service.call(1,new Uint8Array(new SharedArrayBuffer(1))),statusIs(S.invalid_request));
    assert.equal(foundation.receive(new Uint8Array(new SharedArrayBuffer(64))),false);
  }
  await assert.rejects(service.call(1,new Uint8Array(449)),statusIs(S.limit_exceeded));
  assert.equal(fake.submissions.length,count);
  const last=await opened({firstSequence:U64_MAX});
  assert.equal(view(last.fake.submissions[0].bytes).getBigUint64(24,true),U64_MAX);
  await assert.rejects(last.service.call(1,new Uint8Array()),statusIs(S.limit_exceeded));
  assert.equal(last.fake.submissions.length,1,'sequence overflow must never wrap');
});

test('resend is explicit and byte-identical even after caller or adapter mutation',async()=>{
  const {fake,foundation,service}=await opened({}, {...query,source:'native'});
  const payload=Uint8Array.of(10,20);fake.onEnqueue=bytes=>bytes.fill(99);
  const call=service.call(7,payload),original=fake.submissions[1].bytes.slice();payload.fill(4);
  assert.equal(fake.submissions.length,2);await Promise.resolve();assert.equal(fake.submissions.length,2);
  assert.equal(foundation.resend(call.sequence),S.ok);
  assert.deepEqual(fake.submissions[2].bytes,original);assert.equal(fake.submissions[2].source,'automatic');
  assert.equal(fake.deliver(completion(original,{payload:Uint8Array.of(8)})),true);assert.deepEqual(await call,Uint8Array.of(8));
  assert.equal(foundation.resend(call.sequence),S.ok);
  assert.equal(fake.deliver(completion(original,{payload:Uint8Array.of(8)})),true);
  assert.equal(foundation.acknowledge(),S.ok);assert.equal(foundation.resend(call.sequence),S.expired);
  assert.equal(foundation.resend(2),S.invalid_request);
});

test('uncertain admission and uncertain effects never trigger an automatic retry',async()=>{
  const {fake,foundation,service}=await opened({maxRetainedCalls:1});
  fake.onEnqueue=()=>{throw Error('fake admission lost its return');};
  const call=service.call(7,Uint8Array.of(5));await assert.rejects(call,statusIs(S.uncertain));
  await Promise.resolve();assert.equal(fake.submissions.length,2);
  await assert.rejects(service.call(7,new Uint8Array()),statusIs(S.limit_exceeded));
  assert.equal(foundation.acknowledge(),S.ok);assert.deepEqual(fake.acks,[[1n,1n]]);
  fake.onEnqueue=null;assert.equal(foundation.resend(call.sequence),S.ok);
  assert.deepEqual(fake.submissions[2],fake.submissions[1]);
  assert.equal(fake.deliver(completion(fake.submissions[1].bytes,{status:S.uncertain})),true);
  assert.equal(foundation.acknowledge(),S.ok);
  const effect=service.call(8,new Uint8Array()),rejected=assert.rejects(effect,statusIs(S.uncertain));
  assert.equal(fake.deliver(completion(fake.submissions[3].bytes,{status:S.uncertain})),true);await rejected;
  await Promise.resolve();assert.equal(fake.submissions.length,4);assert.equal(foundation.acknowledge(),S.ok);
});

test('explicit expiry resolves uncertain admission gaps without ACKing unadmitted work',async()=>{
  for(const recover of ['resend','cancel']) {
    const {fake,foundation,service}=await opened();
    fake.enqueueStatus=NaN;const unknown=service.call(7,new Uint8Array());
    await assert.rejects(unknown,statusIs(S.uncertain));
    fake.enqueueStatus=S.ok;const later=service.call(8,new Uint8Array());
    assert.equal(fake.deliver(completion(fake.submissions[2].bytes)),true);await later;
    assert.equal(foundation.acknowledge(),S.ok);assert.deepEqual(fake.acks,[[1n,1n]]);
    if(recover==='resend')fake.enqueueStatus=S.expired;else fake.cancelStatus=S.expired;
    assert.equal(foundation[recover](unknown.sequence),S.expired);
    assert.equal(foundation.acknowledge(),S.ok);assert.deepEqual(fake.acks.at(-1),[1n,later.sequence]);
    assert.equal(foundation.resend(unknown.sequence),S.expired);
  }
});

test('explicit replay exposes a definitive result after the original admission was uncertain',async()=>{
  const {fake,foundation,service}=await opened();fake.enqueueStatus=NaN;
  const unknown=service.call(7,Uint8Array.of(6));await assert.rejects(unknown,statusIs(S.uncertain));
  fake.enqueueStatus=S.ok;const replay=foundation.replay(unknown.sequence);
  assert.equal(replay.sequence,unknown.sequence);assert.equal(foundation.replay(unknown.sequence),replay);
  assert.equal(fake.submissions.length,3,'one outstanding replay Promise is shared');
  assert.deepEqual(fake.submissions[2],fake.submissions[1]);
  const bytes=completion(fake.submissions[1].bytes,{payload:Uint8Array.of(9)});
  assert.equal(fake.deliver(bytes),true);const result=await replay;assert.deepEqual(result,Uint8Array.of(9));
  result.fill(0);const again=foundation.replay(unknown.sequence);
  assert.equal(fake.deliver(bytes),true);assert.deepEqual(await again,Uint8Array.of(9));
  const retired=foundation.replay(unknown.sequence),rejected=assert.rejects(retired,statusIs(S.expired));
  assert.equal(foundation.acknowledge(),S.ok);await rejected;
  await assert.rejects(foundation.replay(unknown.sequence),statusIs(S.expired));
});

test('uncertain discovery replay preserves its query/source and can still produce a usable service',async()=>{
  const fake=new FakeTransport(),foundation=createFoundationServices(fake,{generation:1n});fake.foundation=foundation;
  fake.enqueueStatus=undefined;const unknown=foundation.discover('fixture.echo',{...query,source:'module',schema:SCHEMA});
  await assert.rejects(unknown,statusIs(S.uncertain));
  fake.enqueueStatus=S.unavailable;await assert.rejects(foundation.replay(unknown.sequence),statusIs(S.unavailable));
  fake.enqueueStatus=S.ok;const replay=foundation.replay(unknown.sequence);
  assert.deepEqual(fake.submissions[2],fake.submissions[0]);
  assert.equal(fake.deliver(completion(fake.submissions[0].bytes,{payload:tlv(descriptorFields())})),true);
  const service=await replay;assert.equal(foundation.acknowledge(),S.ok);
  const call=service.call(8,Uint8Array.of(3));assert.equal(fake.submissions[3].source,'automatic');
  assert.equal(fake.deliver(completion(fake.submissions[3].bytes,{payload:Uint8Array.of(4)})),true);
  assert.deepEqual(await call,Uint8Array.of(4));assert.equal(foundation.acknowledge(),S.ok);
});

test('definite admission rejection consumes no retention and later ACK closes unused gaps',async()=>{
  const {fake,foundation,service}=await opened({maxRetainedCalls:1});
  fake.enqueueStatus=S.unavailable;const failed=service.call(7,new Uint8Array());
  await assert.rejects(failed,statusIs(S.unavailable));assert.equal(failed.sequence,2n);
  fake.enqueueStatus=S.ok;const call=service.call(7,new Uint8Array());assert.equal(call.sequence,3n);
  assert.equal(fake.deliver(completion(fake.submissions[2].bytes)),true);await call;
  assert.equal(foundation.acknowledge(),S.ok);assert.deepEqual(fake.acks.at(-1),[1n,3n]);
});

test('cancellation settles only on its matching queued completion',async()=>{
  const {fake,foundation,service}=await opened();const call=service.call(7,new Uint8Array());
  const rejected=assert.rejects(call,statusIs(S.closed));
  assert.equal(foundation.cancel(call.sequence),S.ok);assert.deepEqual(fake.cancels,[[1n,call.sequence]]);
  assert.equal(foundation.acknowledge(),S.ok);assert.deepEqual(fake.acks,[[1n,1n]]);
  assert.equal(fake.deliver(completion(fake.submissions[1].bytes,{status:S.closed})),true);await rejected;
  assert.equal(foundation.cancel(call.sequence),S.conflict);assert.equal(foundation.acknowledge(),S.ok);
  assert.equal(foundation.cancel(call.sequence),S.expired);
});

test('adapter reentry cannot deliver or submit work inside admission or ACK',async()=>{
  const {fake,foundation,service}=await opened();let inner;
  fake.onEnqueue=()=>{
    const bytes=fake.submissions.at(-1).bytes;
    assert.equal(foundation.receive(completion(bytes)),false);
    assert.equal(foundation.acknowledge(),S.conflict);
    assert.equal(foundation.resend(view(bytes).getBigUint64(24,true)),S.conflict);
    assert.equal(foundation.cancel(view(bytes).getBigUint64(24,true)),S.conflict);
    inner=assert.rejects(service.call(5,new Uint8Array()),statusIs(S.conflict));
  };
  const call=service.call(4,new Uint8Array());await inner;assert.equal(fake.submissions.length,2);
  fake.onEnqueue=null;assert.equal(fake.deliver(completion(fake.submissions[1].bytes)),true);await call;
  fake.onAcknowledge=()=>{
    assert.equal(foundation.receive(completion(fake.submissions[1].bytes)),false);
    assert.equal(foundation.acknowledge(),S.conflict);
    assert.equal(foundation.cancel(call.sequence),S.conflict);
  };
  fake.acknowledge=()=>{throw Error('captured adapter method is stable');};
  assert.equal(foundation.acknowledge(),S.ok);
});

test('dispose guards retained service closures, late deliveries and a replacement generation',async()=>{
  const {fake,foundation,service}=await opened();const call=service.call(7,new Uint8Array());
  const rejected=assert.rejects(call,statusIs(S.closed));foundation.dispose();foundation.dispose();await rejected;
  assert.equal(fake.deliver(completion(fake.submissions[1].bytes)),false);
  await assert.rejects(service.call(7,new Uint8Array()),statusIs(S.closed));
  await assert.rejects(foundation.discover('fixture.echo',query),statusIs(S.closed));
  assert.equal(foundation.acknowledge(),S.closed);assert.equal(foundation.cancel(call.sequence),S.closed);
  assert.equal(foundation.resend(call.sequence),S.closed);
  const successor=new FakeTransport(),next=createFoundationServices(successor,{generation:2n});successor.foundation=next;
  const discovery=next.discover('fixture.echo',query);
  assert.equal(next.receive(completion(fake.submissions[0].bytes,{payload:tlv(descriptorFields())})),false);
  assert.equal(successor.deliver(completion(successor.submissions[0].bytes,{payload:tlv(descriptorFields())})),true);
  await discovery;assert.equal(next.acknowledge(),S.ok);
});

test('dispose during an adapter callback cannot resurrect a pending request',async()=>{
  const {fake,foundation,service}=await opened();fake.onEnqueue=()=>foundation.dispose();
  const call=service.call(7,new Uint8Array());await assert.rejects(call,statusIs(S.closed));
  assert.equal(fake.deliver(completion(fake.submissions[1].bytes)),false);assert.equal(foundation.acknowledge(),S.closed);
});
