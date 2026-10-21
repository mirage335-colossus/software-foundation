import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';
import { decodeTotal, encodeOperands, PROVIDER_NAME, PROVIDER_SCHEMA, UINT32_MAX, connectQuoteProvider } from '../src-web-appended/quote-pad-protocol.mjs';

const schema = await readFile(new URL('../src-bin-appended/provider-schema.json', import.meta.url));
assert.deepEqual([...PROVIDER_SCHEMA], [...createHash('sha256').update(schema).digest()]);
assert.deepEqual([...encodeOperands(20, 22)], [20,0,0,0,22,0,0,0]);
assert.throws(() => encodeOperands(-1, 0), RangeError);
assert.throws(() => encodeOperands(UINT32_MAX + 1, 0), RangeError);
const response = new Uint8Array(12);
const responseView = new DataView(response.buffer);
responseView.setUint32(0, 43, true);
responseView.setUint32(4, 0, true);
responseView.setUint32(8, 1, true);
assert.deepEqual({ ...decodeTotal(response) }, { total: 43, overflow: false, calls: 1 });
responseView.setUint32(0, 0, true);
responseView.setUint32(4, 1, true);
assert.equal(decodeTotal(response).overflow, true);
responseView.setUint32(0, 5, true);
assert.throws(() => decodeTotal(response), /violates/);
assert.throws(() => decodeTotal(new Uint8Array(11)), /exactly 12/);

let query;
const fakeService = {
  descriptor: { name: PROVIDER_NAME, major: 1, minor: 0, schema: PROVIDER_SCHEMA.slice(), maxReplyBytes: 12 },
  async call(operation, request) {
    assert.equal(operation, 1);
    assert.deepEqual([...request], [...encodeOperands(20, 22)]);
    const reply = new Uint8Array(12);
    const view = new DataView(reply.buffer);
    view.setUint32(0, 43, true); view.setUint32(8, 1, true);
    return reply;
  },
};
const facade = { async discover(name, options) { query = { name, ...options }; return fakeService; } };
const calculator = await connectQuoteProvider(facade);
assert.deepEqual(query, { name: PROVIDER_NAME, major: 1, minMinor: 0, maxMinor: 0, schema: PROVIDER_SCHEMA, source: 'module' });
assert.deepEqual({ ...await calculator(20, 22) }, { total: 43, overflow: false, calls: 1 });
await assert.rejects(connectQuoteProvider({ discover: async () => ({ ...fakeService, descriptor: { ...fakeService.descriptor, maxReplyBytes: 11 } }) }), /does not match/);
console.log('Quote Pad protocol fixtures passed (public-facade shape mocked; module/host execution not exercised).');
