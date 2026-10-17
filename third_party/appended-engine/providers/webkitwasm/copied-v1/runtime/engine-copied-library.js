// SPDX-License-Identifier: CC0-1.0
// One engine-local import. The captured Worker's callback performs engine.read,
// kernel.call and engine.write: owned copies across separate module memories.
// These scalar arguments are never forwarded as pointers into kernel memory.
addToLibrary({
  $bibEngineCopiedHost__deps: ['$wasmMemory', '$HEAPU8'],
  $bibEngineCopiedHost__postset: 'bibEngineCopiedHost.initialize();',
  $bibEngineCopiedHost: {
    callback: null,
    poisoned: false,
    active: false,
    initialize: function() {
      var callback = Module['foundationEngineHost'];
      if (typeof callback !== 'function')
        throw Error('Missing copied engine Worker host');
      this.callback = callback;
    },
    trap: function() {
      this.poisoned = true;
      // A terminal callback must escape the Wasm export, so createCopiedEndpoint
      // poisons it and suppresses frees/destructors. Returning -4 here could let
      // native exception handling turn uncertainty into a clean reply.
      throw new WebAssembly.RuntimeError('Terminal copied engine host failure');
    },
    u32: function(value) {
      // Imported Wasm i32 pointers may arrive signed, including the upper half
      // of a wasm32 memory. Reject JS values that are not actual i32/u32 bits.
      if (!Number.isInteger(value) || value < -2147483648 || value > 4294967295)
        return this.trap();
      return value >>> 0;
    },
    heap: function() {
      // Reacquire after every host invocation, which may grow either endpoint.
      if (!(HEAPU8 instanceof Uint8Array) || !(HEAPU8.buffer instanceof ArrayBuffer) ||
          HEAPU8.byteOffset !== 0 || HEAPU8.byteLength === 0 ||
          HEAPU8.byteLength !== HEAPU8.buffer.byteLength || HEAPU8.buffer !== wasmMemory.buffer)
        return this.trap();
      return HEAPU8;
    },
    span: function(heap, pointer, length) {
      if ((length !== 0 && pointer === 0) || pointer > heap.byteLength ||
          length > heap.byteLength - pointer) return this.trap();
    },
    call: function(operation, input, length, output, capacity) {
      if (this.poisoned || this.active) return this.trap();
      operation = this.u32(operation); input = this.u32(input);
      length = this.u32(length); output = this.u32(output); capacity = this.u32(capacity);
      var heap = this.heap();
      this.span(heap, input, length); this.span(heap, output, capacity);
      if (length && capacity && input < output + capacity && output < input + length)
        return this.trap();
      this.active = true;
      try {
        var result = this.callback(operation, input, length, output, capacity);
        // The pinned Worker returns 0 for notifications or a copied reply byte
        // count. Any negative status, promise, oversized or noninteger result is
        // uncertain after a host call and must terminate this endpoint.
        if (!Number.isInteger(result) || result < 0 || result > capacity)
          return this.trap();
        heap = this.heap();
        this.span(heap, input, length); this.span(heap, output, capacity);
        return result;
      } catch (_) {
        return this.trap();
      } finally {
        this.active = false;
      }
    }
  },
  bib_engine_copied_host_v1__deps: ['$bibEngineCopiedHost'],
  bib_engine_copied_host_v1__sig: 'iiiiii',
  bib_engine_copied_host_v1: function(operation, input, length, output, capacity) {
    return bibEngineCopiedHost.call(operation, input, length, output, capacity);
  }
});
