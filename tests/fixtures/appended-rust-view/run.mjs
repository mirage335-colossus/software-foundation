import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const golden = JSON.parse(readFileSync(new URL('./view-wire-v1-golden.json', import.meta.url), 'utf8'));
const modulePath = process.argv[2];
assert.ok(modulePath, 'usage: node run.mjs /absolute/path/to/rust-view-fixture.wasm');

const bytes = readFileSync(modulePath);
const viewHandle = 7n;
const operation = 1;
const generation = BigInt(golden.generation_u64);
let calls = 0;
let instance;

function field(id, type, value) {
  const header = Buffer.alloc(8);
  header.writeUInt16LE(id, 0);
  header.writeUInt8(type, 2);
  header.writeUInt8(1, 3);
  header.writeUInt32LE(value.length, 4);
  return Buffer.concat([header, value]);
}

function u32(value) {
  const out = Buffer.alloc(4);
  out.writeUInt32LE(value, 0);
  return out;
}

function u64(value) {
  const out = Buffer.alloc(8);
  out.writeBigUInt64LE(value, 0);
  return out;
}

function envelope(message) {
  assert.ok(message.length >= 64, 'truncated envelope');
  const total = message.readUInt32LE(0);
  assert.equal(total, message.length, 'envelope total length');
  assert.equal(message.readUInt16LE(4), 1, 'ABI major');
  assert.equal(message.readUInt16LE(6), 0, 'ABI minor');
  assert.equal(message.readUInt32LE(12), 0, 'envelope flags');
  assert.equal(message.readUInt32LE(52), 0, 'reserved word');
  assert.equal(message.readUInt32LE(44), message.length - 64, 'payload length');
  return {
    kind: message.readUInt32LE(8),
    generation: message.readBigUInt64LE(16),
    sequence: message.readBigUInt64LE(24),
    handle: message.readBigUInt64LE(32),
    operation: message.readUInt32LE(40),
    status: message.readUInt32LE(48),
  };
}

function makeReply(request, payload) {
  const header = Buffer.alloc(64);
  header.writeUInt32LE(64 + payload.length, 0);
  header.writeUInt16LE(1, 4);
  header.writeUInt16LE(0, 6);
  header.writeUInt32LE(2, 8);
  header.writeUInt32LE(0, 12);
  header.writeBigUInt64LE(request.generation, 16);
  header.writeBigUInt64LE(request.sequence, 24);
  header.writeBigUInt64LE(request.handle, 32);
  header.writeUInt32LE(request.operation, 40);
  header.writeUInt32LE(payload.length, 44);
  header.writeUInt32LE(0, 48);
  header.writeUInt32LE(0, 52);
  header.writeBigUInt64LE(0n, 56);
  return Buffer.concat([header, payload]);
}

function hostCall(requestOffset, requestBytes, replyOffset, replyCapacity) {
  calls += 1;
  assert.equal(calls, 1, 'fixture makes exactly one host call');
  const memory = Buffer.from(instance.exports.memory.buffer);
  const requestEnd = requestOffset + requestBytes;
  const replyEnd = replyOffset + replyCapacity;
  assert.ok(requestOffset > 0 && requestEnd <= memory.length, 'request range is in guest memory');
  assert.ok(replyOffset > 0 && replyEnd <= memory.length, 'reply range is in guest memory');
  assert.ok(requestEnd <= replyOffset || replyEnd <= requestOffset, 'request and reply do not overlap');

  const requestBytesCopy = Buffer.from(memory.subarray(requestOffset, requestEnd));
  const request = envelope(requestBytesCopy);
  assert.equal(request.kind, 1, 'view replacement is a request');
  assert.equal(request.generation, generation, 'generation preserves the exact u64 above 2^53');
  assert.equal(request.sequence, 1n, 'first request sequence');
  assert.equal(request.handle, viewHandle, 'view interface handle');
  assert.equal(request.operation, operation, 'view replace operation');
  assert.equal(request.status, 0, 'request service status');

  const payload = requestBytesCopy.subarray(64);
  assert.equal(payload.toString('hex'), golden.replace_payload_hex, 'complete replace payload golden');
  const payloadFields = parseRecord(payload);
  assert.deepEqual(payloadFields.map(field => field.id), [1,2,3,4,5,6]);
  assert.equal(payloadFields[5].type, 9, 'widgets field is a record list');
  const widgetList = payloadFields[5].value;
  assert.equal(widgetList.readUInt32LE(0), 1, 'one widget in snapshot');
  const widgetBytes = widgetList.subarray(8, 8 + widgetList.readUInt32LE(4));
  assert.equal(widgetBytes.toString('hex'), golden.widget_hex, 'complete widget record golden');
  const widgetFields = parseRecord(widgetBytes);
  assert.equal(widgetFields[0].value.toString('utf8'), 'tile');
  assert.equal(widgetFields[1].value.readBigUInt64LE(0), generation, 'widget generation is exact u64');
  assert.equal(widgetFields[2].value.readUInt32LE(0), 3, 'button kind');
  assert.equal(widgetFields[3].value.toString('hex'), golden.rect_hex, 'complete rect record golden');

  const acceptedRevision = field(1, 2, u64(1n));
  const reply = makeReply(request, acceptedRevision);
  assert.ok(reply.length <= replyCapacity, 'reply fits host-provided capacity');
  memory.set(reply, replyOffset);
  return 0;
}

function parseRecord(record) {
  const fields = [];
  let offset = 0;
  let previous = 0;
  while (offset < record.length) {
    assert.ok(record.length - offset >= 8, 'complete TLV header');
    const id = record.readUInt16LE(offset);
    const type = record.readUInt8(offset + 2);
    const flags = record.readUInt8(offset + 3);
    const length = record.readUInt32LE(offset + 4);
    assert.ok(id > previous, 'canonical increasing field ids');
    assert.equal(flags, 1, 'fixture fields are must-understand');
    assert.ok(length <= record.length - offset - 8, 'field value stays in record');
    fields.push({ id, type, value: record.subarray(offset + 8, offset + 8 + length) });
    previous = id;
    offset += 8 + length;
  }
  return fields;
}

function contextRecord() {
  const schema = Buffer.from('47684bc0172f088d6805b7d49224f4975308e895f6e47824e51673ddd8b86890', 'hex');
  return Buffer.concat([
    field(1, 2, u64(generation)),
    field(2, 1, u32(0x00010000)),
    field(3, 1, u32(64)),
    field(4, 1, u32(1_048_576)),
    field(5, 7, schema),
    field(6, 1, u32(8)),
    field(7, 1, u32(4)),
    field(8, 1, u32(4096)),
  ]);
}

const imports = { 'foundation.kernel.v1': { call: hostCall } };
const result = await WebAssembly.instantiate(bytes, imports);
instance = result.instance;
const exports = instance.exports;
assert.equal(exports.foundation_app_abi_v1(), 0x00010000, 'guest ABI version');
const memory = new Uint8Array(exports.memory.buffer);
const context = contextRecord();
const contextOffset = exports.foundation_app_alloc_v1(context.length);
assert.ok(contextOffset > 0 && (contextOffset & 15) === 0, 'runtime context allocation is nonzero and aligned');
memory.set(context, contextOffset);
assert.equal(exports.foundation_app_init_v1(contextOffset, context.length), 0, 'view fixture initializes');
exports.foundation_app_free_v1(contextOffset, context.length);
assert.equal(calls, 1, 'initialize published exactly one view snapshot');
assert.equal(exports.foundation_app_step_v1(1), 0, 'step remains idle');
exports.foundation_app_shutdown_v1(0);
console.log('Rust foundation.view v1 Wasm fixture passed: exact rect/widget/snapshot goldens and validator vectors.');
