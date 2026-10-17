// SPDX-License-Identifier: CC0-1.0
// Factory-local input checks. This file neither starts an engine nor changes
// the Worker's exact own-Wasm/data locator. The compiled incoming API must
// explicitly receive wasmBinary; the pinned SDK's default omits it.
(() => {
  if (typeof WorkerGlobalScope !== 'function' ||
      !(globalThis instanceof WorkerGlobalScope) ||
      typeof DedicatedWorkerGlobalScope !== 'function' ||
      !(globalThis instanceof DedicatedWorkerGlobalScope) ||
      typeof self === 'undefined' || self !== globalThis ||
      typeof ENVIRONMENT_IS_WORKER === 'undefined' || !ENVIRONMENT_IS_WORKER ||
      typeof ENVIRONMENT_IS_WEB !== 'undefined' && ENVIRONMENT_IS_WEB ||
      typeof ENVIRONMENT_IS_NODE !== 'undefined' && ENVIRONMENT_IS_NODE ||
      typeof ENVIRONMENT_IS_SHELL !== 'undefined' && ENVIRONMENT_IS_SHELL ||
      typeof ENVIRONMENT_IS_PTHREAD !== 'undefined' && ENVIRONMENT_IS_PTHREAD ||
      typeof ENVIRONMENT_IS_WASM_WORKER !== 'undefined' && ENVIRONMENT_IS_WASM_WORKER)
    throw Error('Copied engine requires its direct dedicated browser Worker');
  const typed = Object.getPrototypeOf(Uint8Array.prototype);
  const read = name => Object.getOwnPropertyDescriptor(typed, name).get;
  const tag = read(Symbol.toStringTag), buffer = read('buffer');
  const offset = read('byteOffset'), length = read('byteLength');
  const binary = Module['wasmBinary'];
  let data, size;
  try {
    if (tag.call(binary) !== 'Uint8Array') throw Error();
    data = buffer.call(binary); size = length.call(binary);
    if (!(data instanceof ArrayBuffer) || offset.call(binary) !== 0 ||
        size === 0 || size > 256 * 1048576 || size !== data.byteLength) throw Error();
  } catch (_) {
    throw Error('Copied engine requires complete owned nonshared Wasm bytes');
  }
  if (Module['noInitialRun'] !== true || typeof Module['locateFile'] !== 'function' ||
      typeof Module['foundationEngineHost'] !== 'function')
    throw Error('Copied engine requires deferred startup and its retained Worker host');
  // Own a factory-local copy before asynchronous instantiation can yield. No
  // bytes are fetched and no Blob-relative name or fallback URL is invented.
  Module['wasmBinary'] = new Uint8Array(new Uint8Array(data, 0, size));
})();
