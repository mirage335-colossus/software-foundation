export const UINT32_MAX = 0xffff_ffff;
export const PROVIDER_NAME = 'org.example.quote.total';
export const PROVIDER_SCHEMA = new Uint8Array([
  0xba,0xa7,0xae,0x88,0xe0,0x6a,0x98,0x59,
  0x99,0x0d,0x80,0xf9,0x9f,0x23,0x86,0xe0,
  0x19,0xde,0x22,0x3c,0x9b,0xb8,0xe5,0xa8,
  0x9f,0x4d,0x8f,0xd0,0xab,0x45,0x65,0x3f,
]);

export function encodeOperands(left, right) {
  for (const value of [left, right]) {
    if (!Number.isInteger(value) || value < 0 || value > UINT32_MAX)
      throw new RangeError('Amounts must be unsigned 32-bit integers');
  }
  const bytes = new Uint8Array(8);
  const view = new DataView(bytes.buffer);
  view.setUint32(0, left, true);
  view.setUint32(4, right, true);
  return bytes;
}

export function decodeTotal(bytes) {
  if (!(bytes instanceof Uint8Array) || bytes.byteLength !== 12)
    throw new TypeError('Provider reply must contain exactly 12 bytes');
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const total = view.getUint32(0, true);
  const overflow = view.getUint32(4, true);
  const calls = view.getUint32(8, true);
  if (overflow > 1 || (overflow === 1 && total !== 0))
    throw new TypeError('Provider reply violates the checked-total schema');
  return Object.freeze({ total, overflow: overflow === 1, calls });
}

export async function connectQuoteProvider(foundation = globalThis.foundation) {
  if (!foundation || typeof foundation.discover !== 'function')
    throw new Error('The appended-application service facade is unavailable');
  const service = await foundation.discover(PROVIDER_NAME, {
    major: 1, minMinor: 0, maxMinor: 0, schema: PROVIDER_SCHEMA, source: 'module',
  });
  const descriptor = service?.descriptor;
  if (!descriptor || descriptor.name !== PROVIDER_NAME || descriptor.major !== 1 ||
      descriptor.minor !== 0 || descriptor.maxReplyBytes !== 12 ||
      !(descriptor.schema instanceof Uint8Array) ||
      descriptor.schema.byteLength !== PROVIDER_SCHEMA.byteLength ||
      descriptor.schema.some((byte, index) => byte !== PROVIDER_SCHEMA[index]) ||
      typeof service.call !== 'function')
    throw new Error('The discovered provider does not match Quote Pad schema v1');
  return async (left, right) => decodeTotal(await service.call(1, encodeOperands(left, right)));
}
