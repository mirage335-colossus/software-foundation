import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const golden = JSON.parse(readFileSync(new URL('./view-provider-golden.json', import.meta.url), 'utf8'));
const wasmPath = process.argv[2];
assert.ok(wasmPath, 'usage: node run.mjs /absolute/path/to/rust-both-application.wasm');
const wasm = readFileSync(wasmPath);
const optionalCase = process.argv[3]?.startsWith('--optional-') ? process.argv[3].slice(11) : null;
let providerDiscoverySequence = null;
const wrongRevisionField = process.argv[3] === '--wrong-revision-field';
const wrongTargetType = process.argv[3] === '--wrong-target-type';
const generation = BigInt(wrongRevisionField ? '1' : golden.generation_u64);
const handles = { view: BigInt(golden.view_handle_u64), providers: BigInt(golden.provider_service_handle_u64), token: BigInt(golden.provider_token_u64) };
let instance;
let callCount = 0;
let snapshots = [];
let providerReply;
const providerReplies = [];
let activeProvider = null;
let highestCompleted = 0n;
let acknowledgedThrough = 0n;
const completed = new Set();

const le = (value, size) => {
  const b = Buffer.alloc(size);
  if (size === 4) b.writeUInt32LE(value, 0); else b.writeBigUInt64LE(BigInt(value), 0);
  return b;
};
function field(id, type, value) {
  const h = Buffer.alloc(8); h.writeUInt16LE(id); h[2] = type; h[3] = 1; h.writeUInt32LE(value.length, 4);
  return Buffer.concat([h, value]);
}
function record(fields) { return Buffer.concat(fields); }
function number(value) { const out = Buffer.alloc(8); out.writeDoubleLE(value); return out; }
function required(fields, id, type) {
  const field = fields.find(item => item.id === id);
  assert.ok(field, `required field ${id}`); assert.equal(field.type, type, `field ${id} wire type`);
  return field.value;
}
function snapshotWire(state) {
  const definitions = [['lhs',6,20,'Left operand',state.lhs],['rhs',6,70,'Right operand',state.rhs],
    ['sum',3,120,'Sum',''],['result',2,170,'Result',state.result]];
  const children = definitions.map(([id,kind,y,label,text]) => {
    const rect = record([field(1,4,number(20)),field(2,4,number(y)),field(3,4,number(360)),field(4,4,number(32))]);
    const fields = [field(1,6,Buffer.from(id)),field(2,2,le(1n,8)),field(3,1,le(kind,4)),
      field(4,8,rect),field(7,6,Buffer.from(text)),field(8,6,Buffer.from(label))];
    if (kind === 6) fields.push(field(18,1,le(10,4)),field(19,1,le(2,4)));
    const child = record(fields); return Buffer.concat([le(child.length,4),child]);
  });
  return record([field(1,2,le(state.revision_u64,8)),field(2,6,Buffer.from(golden.view_title)),
    field(3,4,number(state.width)),field(4,4,number(state.height)),field(5,4,number(state.scale)),
    field(6,9,Buffer.concat([le(4,4),...children]))]);
}
function parse(bytes) {
  const out = []; let at = 0, last = 0;
  while (at < bytes.length) {
    assert.ok(bytes.length - at >= 8, 'full TLV header');
    const id = bytes.readUInt16LE(at), type = bytes[at + 2], flags = bytes[at + 3], n = bytes.readUInt32LE(at + 4);
    assert.ok(id > last, 'canonical increasing record ids'); assert.equal(flags, 1, 'required canonical fields');
    assert.ok(n <= bytes.length - at - 8, 'field is inside record');
    out.push({ id, type, value: bytes.subarray(at + 8, at + 8 + n) }); last = id; at += 8 + n;
  }
  return out;
}
function envelope(bytes) {
  assert.ok(bytes.length >= 64);
  assert.equal(bytes.readUInt32LE(0), bytes.length);
  assert.equal(bytes.readUInt16LE(4), 1); assert.equal(bytes.readUInt16LE(6), 0);
  assert.equal(bytes.readUInt32LE(12), 0); assert.equal(bytes.readUInt32LE(52), 0);
  assert.equal(bytes.readUInt32LE(44), bytes.length - 64);
  return { kind: bytes.readUInt32LE(8), generation: bytes.readBigUInt64LE(16), sequence: bytes.readBigUInt64LE(24),
    handle: bytes.readBigUInt64LE(32), operation: bytes.readUInt32LE(40), status: bytes.readUInt32LE(48), correlation: bytes.readBigUInt64LE(56), payload: bytes.subarray(64) };
}
function replyTo(request, status, payload = Buffer.alloc(0)) {
  const out = Buffer.alloc(64); out.writeUInt32LE(64 + payload.length, 0); out.writeUInt16LE(1, 4);
  out.writeUInt16LE(0, 6); out.writeUInt32LE(2, 8); out.writeUInt32LE(0, 12);
  out.writeBigUInt64LE(request.generation, 16); out.writeBigUInt64LE(request.sequence, 24);
  out.writeBigUInt64LE(request.handle, 32); out.writeUInt32LE(request.operation, 40);
  out.writeUInt32LE(payload.length, 44); out.writeUInt32LE(status, 48); out.writeUInt32LE(0, 52); out.writeBigUInt64LE(0n, 56);
  return Buffer.concat([out, payload]);
}
function hostCall(reqPtr, reqBytes, repPtr, repCapacity) {
  callCount++;
  const mem = Buffer.from(instance.exports.memory.buffer);
  assert.ok(reqPtr > 0 && repPtr > 0 && reqPtr + reqBytes <= mem.length && repPtr + repCapacity <= mem.length,
    'host call request/reply ranges remain in guest memory');
  assert.ok(reqPtr + reqBytes <= repPtr || repPtr + repCapacity <= reqPtr, 'request/reply ranges do not overlap');
  const req = envelope(Buffer.from(mem.subarray(reqPtr, reqPtr + reqBytes)));
  assert.equal(req.kind, 1, 'guest host calls are requests');
  assert.equal(req.generation, generation, 'all calls preserve exact u64 generation');
  assert.equal(req.status, 0); assert.equal(req.correlation, 0n);
  assert.ok(req.sequence > highestCompleted, 'guest request sequences increase');
  let status = 0, payload = Buffer.alloc(0);
  if (req.handle === 0n && req.operation === 1) {
    const query = parse(req.payload); const name = query[0].value.toString();
    assert.deepEqual(query.map(x => x.id), [1,2,3,4,5]);
    assert.equal(required(query,1,6).toString(), name);
    assert.equal(required(query,2,1).readUInt32LE(),1);
    assert.equal(required(query,3,1).readUInt32LE(),0);
    assert.equal(required(query,4,1).readUInt32LE(),0);
    if (name === 'foundation.view') {
      assert.deepEqual(query.map(x => x.id), [1,2,3,4,5]);
      assert.equal(query[4].value.toString('hex'), '7345dda570c5c338f41785c88ebea3f7ba78eff7da07786a0ced43fe4dc411b7');
      payload = record([field(1, 2, le(handles.view, 8)), field(2, 6, Buffer.from('foundation.view')),
        field(3, 1, le(1, 4)), field(4, 1, le(0, 4)), field(5, 7, Buffer.from('7345dda570c5c338f41785c88ebea3f7ba78eff7da07786a0ced43fe4dc411b7', 'hex')),
        field(6, 1, le(32768, 4))]);
    } else {
      assert.equal(name, 'foundation.providers');
      providerDiscoverySequence = req.sequence;
      assert.equal(required(query,5,7).toString('hex'),'846fd7a2aa16758db702aa30791730ab6de6635a50ba90234995cb06a7ec93de');
      payload = record([field(1, 2, le(handles.providers, 8)), field(2, 6, Buffer.from(name)),
        field(3, 1, le(1, 4)), field(4, 1, le(0, 4)),
        field(5, 7, Buffer.from('846fd7a2aa16758db702aa30791730ab6de6635a50ba90234995cb06a7ec93de', 'hex')),
        field(6, 1, le(32768, 4))]);
      if (['missing', 'missing-ack-not-found', 'missing-payload'].includes(optionalCase)) {
        status = 3; payload = optionalCase === 'missing-payload' ? Buffer.from([0]) : Buffer.alloc(0);
      } else if (optionalCase === 'unavailable') { status = 2; payload = Buffer.alloc(0); }
    }
  } else if (req.handle === handles.providers && req.operation === 1) {
    const registration = parse(req.payload);
    assert.deepEqual(registration.map(x => x.id), [1,2,3,4,5,6]);
    assert.equal(registration[0].value.toString(), 'org.example.increment');
    assert.equal(required(registration,2,1).readUInt32LE(),1);assert.equal(required(registration,3,1).readUInt32LE(),0);
    assert.equal(registration[3].value.toString('hex'), golden.increment_schema_sha256);
    assert.equal(registration[4].value.readUInt32LE(), 4); assert.equal(registration[5].value.readUInt32LE(), 8);
    payload = field(1, 2, le(handles.token, 8));
  } else if (req.handle === handles.view && req.operation === 1) {
    const fields = parse(req.payload); assert.deepEqual(fields.map(x => x.id), [1,2,3,4,5,6]);
    const expected = golden.view_snapshots[snapshots.length];
    assert.ok(expected, 'only the selected application snapshots may publish');
    assert.equal(req.payload.toString('hex'),snapshotWire(expected).toString('hex'),'complete application view snapshot wire golden');
    const revision = fields[0].value.readBigUInt64LE();
    const widgets = fields[5].value; assert.equal(widgets.readUInt32LE(), 4);
    const children = []; let at = 4;
    for (let i = 0; i < 4; i++) { const n = widgets.readUInt32LE(at); at += 4; children.push(parse(widgets.subarray(at, at+n))); at += n; }
    assert.equal(at, widgets.length);
    const state = { revision, title: required(fields,2,6).toString(), lhs: required(children[0],7,6).toString(),
      rhs: required(children[1],7,6).toString(), result: required(children[3],7,6).toString() };
    snapshots.push(state);
    assert.equal(state.title, golden.view_title);
    payload = field(wrongRevisionField ? 2 : 1, 2, le(revision + 1n, 8));
  } else if (req.handle === 0n && req.operation === 5) {
    const ack = parse(req.payload);
    assert.deepEqual(ack.map(x => x.id), [1], 'acknowledge uses the published one-field record');
    assert.equal(ack[0].type, 2, 'acknowledge through_sequence is u64');
    const through = ack[0].value.readBigUInt64LE();
    assert.ok(through > acknowledgedThrough && through < req.sequence && through <= highestCompleted,
      'acknowledgement retires only previously completed guest requests');
    for (const sequence of completed) if (sequence <= through) completed.delete(sequence);
    acknowledgedThrough = through;
    if (through === providerDiscoverySequence && ['ack-not-found', 'missing-ack-not-found'].includes(optionalCase)) status = 3;
  } else if (req.handle === handles.providers && req.operation === 2) {
    const response = parse(req.payload); assert.deepEqual(response.map(x => x.id), [1,2,3,4]);
    assert.ok(activeProvider,'responses occur during an actual provider dispatch');
    assert.equal(required(response,1,2).readBigUInt64LE(),activeProvider.correlation);
    assert.equal(required(response,2,2).readBigUInt64LE(),handles.token);
    assert.equal(required(response,3,1).readUInt32LE(),activeProvider.status);
    const bytes=required(response,4,7);
    if(activeProvider.status===0){assert.equal(bytes.length,8);providerReply=[bytes.readUInt32LE(),bytes.readUInt32LE(4)];
      assert.deepEqual(providerReply,activeProvider.reply);}
    else assert.equal(bytes.length,0,'invalid calls have no response payload');
    providerReplies.push({correlation:activeProvider.correlation.toString(),status:activeProvider.status,
      payload_hex:bytes.toString('hex')});
  } else {
    assert.fail(`unexpected host call handle=${req.handle} operation=${req.operation}`);
  }
  const out = replyTo(req, status, payload); assert.ok(out.length <= repCapacity);
  mem.set(out, repPtr);
  highestCompleted = req.sequence;
  completed.add(req.sequence);
  return 0;
}

const result = await WebAssembly.instantiate(wasm, { 'foundation.kernel.v1': { call: hostCall } });
instance = result.instance;
const ex = instance.exports;
assert.equal(ex.foundation_app_abi_v1(), 0x00010000);
const memory = new Uint8Array(ex.memory.buffer);
const bootstrapSchema = Buffer.from('47684bc0172f088d6805b7d49224f4975308e895f6e47824e51673ddd8b86890', 'hex');
const context = record([field(1,2,le(generation,8)), field(2,1,le(0x00010000,4)), field(3,1,le(64,4)),
  field(4,1,le(1_048_576,4)), field(5,7,bootstrapSchema), field(6,1,le(16,4)), field(7,1,le(8,4)), field(8,1,le(8192,4))]);
const contextPtr = ex.foundation_app_alloc_v1(context.length); assert.ok(contextPtr > 0);
new Uint8Array(ex.memory.buffer).set(context, contextPtr);
const initialized=ex.foundation_app_init_v1(contextPtr, context.length);
ex.foundation_app_free_v1(contextPtr, context.length);
if(optionalCase){
  const missing = optionalCase === 'missing';
  assert.equal(initialized, missing ? 0 : 2, 'only acknowledged absent gateway permits view-only startup');
  assert.equal(snapshots.length, missing ? 1 : 0, 'failed discovery/ACK has no view effect');
  assert.equal(callCount, optionalCase === 'missing-payload' ? 3 : missing ? 6 : 4);
  const before = callCount;ex.foundation_app_shutdown_v1(0);assert.equal(callCount,before);
  console.log(JSON.stringify({status:'passed',case:optionalCase,guest_status:initialized,view_snapshots:snapshots.length,host_calls:callCount,shutdown_returned:true}));
}else if(wrongRevisionField){
  assert.equal(initialized,2,'guest rejects accepted-revision field with wrong ID');
  assert.equal(snapshots.length,1);ex.foundation_app_shutdown_v1(0);
  console.log(JSON.stringify({status:'passed',case:'wrong-revision-field-rejected',guest_status:initialized,host_calls:callCount}));
}else{
assert.equal(initialized, 0, 'combined guest discovers, registers and publishes');

function event(handle, operation, payload, correlation = 0n) {
  const e = Buffer.alloc(64); e.writeUInt32LE(64 + payload.length, 0); e.writeUInt16LE(1,4); e.writeUInt16LE(0,6);
  e.writeUInt32LE(3,8); e.writeUInt32LE(0,12); e.writeBigUInt64LE(generation,16); e.writeBigUInt64LE(500n + BigInt(snapshots.length),24);
  e.writeBigUInt64LE(handle,32); e.writeUInt32LE(operation,40); e.writeUInt32LE(payload.length,44); e.writeUInt32LE(0,48); e.writeUInt32LE(0,52); e.writeBigUInt64LE(correlation,56);
  return Buffer.concat([e,payload]);
}
function dispatch(bytes, expected = 0) { const p = ex.foundation_app_alloc_v1(bytes.length); assert.ok(p>0);
  new Uint8Array(ex.memory.buffer).set(bytes,p); const code = ex.foundation_app_dispatch_v1(p,bytes.length);
  ex.foundation_app_free_v1(p,bytes.length); assert.equal(code,expected); }
function viewInput(revision, id, value, base, kind = 3) {
  const target = record([field(1,6,Buffer.from(id)),field(2,2,le(1,8))]);
  return record([field(1,2,le(revision,8)),field(2,1,le(1,4)),field(3,8,target),field(4,1,le(kind,4)),field(5,6,Buffer.from(value)),field(6,6,Buffer.from(base))]);
}
if(wrongTargetType){
const beforeInvalid=callCount;
dispatch(event(handles.view,1,record([field(1,2,le(1n,8)),field(2,1,le(1,4)),
  field(3,7,record([field(1,6,Buffer.from('lhs')),field(2,2,le(1n,8))])),field(4,1,le(3,4)),
  field(5,6,Buffer.from('17')),field(6,6,Buffer.from('0'))])),1);
assert.equal(callCount,beforeInvalid,'wrong target record type has no host/publication effects');
assert.equal(ex.foundation_app_alloc_v1(16),0,'invalid-input dispatch closes the common runtime');
ex.foundation_app_shutdown_v1(0);
console.log(JSON.stringify({status:'passed',case:'wrong-target-type-rejected',guest_status:1,
  no_host_effects:true,runtime_fail_closed:true,shutdown_returned:true}));
}else{
dispatch(event(handles.view,1,viewInput(1n,'lhs','17','0')));
dispatch(event(handles.view,1,viewInput(2n,'rhs','25','0')));
dispatch(event(handles.view,1,record([field(1,2,le(3n,8)),field(2,1,le(1,4)),field(3,8,record([field(1,6,Buffer.from('sum')),field(2,2,le(1,8))])),field(4,1,le(1,4))])));
assert.equal(snapshots.at(-1).lhs, '17'); assert.equal(snapshots.at(-1).rhs, '25'); assert.equal(snapshots.at(-1).result, '42');
dispatch(event(handles.view,1,record([field(1,2,le(4n,8)),field(2,1,le(3,4)),field(11,4,number(480)),field(12,4,number(280)),field(13,4,number(1.5))])));
dispatch(event(handles.view,1,viewInput(5n,'lhs','4294967295','17')));
dispatch(event(handles.view,1,viewInput(6n,'rhs','0','25')));
const action=(revision,id,kind)=>record([field(1,2,le(revision,8)),field(2,1,le(1,4)),
  field(3,8,record([field(1,6,Buffer.from(id)),field(2,2,le(1n,8))])),field(4,1,le(kind,4))]);
dispatch(event(handles.view,1,action(7n,'lhs',7)));
dispatch(event(handles.view,1,viewInput(8n,'rhs','1','0')));
dispatch(event(handles.view,1,action(9n,'sum',1)));
dispatch(event(handles.view,1,viewInput(10n,'lhs','x','4294967295')));
dispatch(event(handles.view,1,action(11n,'rhs',7)));
for(const [index,test] of golden.provider_calls.entries()){
  activeProvider={...test,correlation:77n+BigInt(index)};
  const bytes=test.payload_hex===undefined?le(test.operand_u32,4):Buffer.from(test.payload_hex,'hex');
  const providerEvent=record([field(1,2,le(handles.token,8)),field(2,1,le(test.operation,4)),field(3,7,bytes)]);
  dispatch(event(handles.providers,1,providerEvent,activeProvider.correlation));activeProvider=null;
}
assert.equal(snapshots.length,golden.view_snapshots.length);
assert.equal(providerReplies.length,golden.provider_calls.length);
assert.ok(callCount >= 12, 'both interfaces used real host dispatches');
assert.equal(ex.foundation_app_step_v1(1), 0); ex.foundation_app_shutdown_v1(0);
assert.deepEqual([...completed],[highestCompleted],'only the final acknowledgement itself remains live at shutdown');
console.log(JSON.stringify({status:'passed',view_snapshots:snapshots.length,provider_replies:providerReplies,
  calculator_17_25_result:'42',resize_and_enter:true,invalid_input_and_overflow:true,generation:generation.toString(),
  host_calls:callCount,last_ack_sequence:acknowledgedThrough.toString(),call_stack_closed:true,shutdown_returned:true}));
}
}
