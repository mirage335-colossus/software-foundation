// Bounded content capability. Files and URLs stay in the host; only owned UTF-8
// text enters the ordered service reply. Export success means download offered.
const maximum = 65536;
function byteLimit(value) {
  const limit = Number(value);
  if (!Number.isSafeInteger(limit) || limit < 0 || limit > maximum) throw new Error('Invalid file service byte limit');
  return limit;
}
export async function readTextFile(file, requestedLimit) {
  const limit = byteLimit(requestedLimit);
  if (!file || !Number.isSafeInteger(file.size) || file.size < 0 || file.size > limit)
    throw new Error(`Select a file no larger than ${limit} bytes`);
  // Slice and recheck protect against a provider returning more than advertised.
  const bytes = await file.slice(0, limit + 1).arrayBuffer();
  if (bytes.byteLength > limit) throw new Error('Selected file exceeds the byte limit');
  return new TextDecoder('utf-8', {fatal: true, ignoreBOM: true}).decode(bytes);
}
const chunkBytes = 4096;
const hex = bytes => Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
function unhex(value) {
  if (typeof value !== 'string' || value.length > chunkBytes * 2 || value.length % 2 || !/^[0-9a-f]*$/.test(value))
    throw new Error('Invalid export chunk');
  return Uint8Array.from(value.match(/../g) || [], pair => parseInt(pair, 16));
}
async function request(exchange, operation, signal) {
  if (signal?.aborted) throw new Error('File operation cancelled');
  const state = await exchange(operation);
  if (signal?.aborted) throw new Error('File operation cancelled');
  if (state.error && state.error !== 'Duplicate operation ignored') throw new Error(state.error);
  if (state.service?.id !== operation.id) throw new Error('File request was replaced');
  return state;
}
// One acknowledged chunk at a time bounds Worker/HTTP queues and gives the
// browser event loop a chance to process input between storage operations.
export async function uploadTextFile(file, service, exchange, signal) {
  const limit = byteLimit(service.byteLimit);
  if (!file || !Number.isSafeInteger(file.size) || file.size < 0 || file.size > limit)
    throw new Error(`Select a file no larger than ${limit} bytes`);
  await request(exchange, {type: 'fileBegin', id: service.id, total: String(file.size)}, signal);
  const decoder = new TextDecoder('utf-8', {fatal: true, ignoreBOM: true});
  for (let offset = 0; offset < file.size; offset += chunkBytes) {
    const count = Math.min(chunkBytes, file.size - offset);
    const bytes = new Uint8Array(await file.slice(offset, offset + count).arrayBuffer());
    if (bytes.length !== count) throw new Error('Selected file changed or was truncated');
    decoder.decode(bytes, {stream: true});
    await request(exchange, {type: 'fileChunk', id: service.id, offset: String(offset), hex: hex(bytes)}, signal);
  }
  decoder.decode();
  // The caller sends finish through the same ordered client after closing its
  // dialog. Only this final operation commits content to the application.
  return {type: 'fileFinish', id: service.id};
}
export async function downloadTextFile(service, exchange, signal) {
  const limit = byteLimit(service.byteLimit), total = Number(service.byteSize);
  if (!Number.isSafeInteger(total) || total < 0 || total > limit) throw new Error('Invalid export size');
  const chunks = [];
  for (let offset = 0; offset < total; offset += chunkBytes) {
    const state = await request(exchange, {type: 'fileRead', id: service.id, offset: String(offset)}, signal);
    const part = state.transfer;
    if (part?.id !== service.id || part.offset !== String(offset) || part.total !== String(total)) throw new Error('Wrong export chunk identity');
    const bytes = unhex(part.hex);
    if (bytes.length !== Math.min(chunkBytes, total - offset)) throw new Error('Truncated export chunk');
    chunks.push(bytes);
  }
  return chunks;
}
export async function executeFileService(service, host = globalThis) {
  const base = {type: 'service', id: service.id, value: '', error: ''};
  if (!host.document || ![5, 6].includes(service.kind))
    return {...base, status: 'error', error: 'File content services are unavailable'};
  let limit;
  try {
    limit = byteLimit(service.byteLimit);
    if (typeof service.value !== 'string' || new TextEncoder().encode(service.value).length > limit)
      throw new Error('File content exceeds the byte limit');
  } catch (error) { return {...base, status: 'error', error: error.message}; }
  return new Promise(resolve => {
    const document = host.document, previous = document.activeElement;
    const dialog = document.createElement('dialog'), form = document.createElement('form');
    dialog.className = 'service-prompt';
    const title = document.createElement('p'), input = document.createElement('input');
    const status = document.createElement('p'), cancel = document.createElement('button'), accept = document.createElement('button');
    title.textContent = service.title; status.setAttribute('role', 'status');
    input.type = 'file'; input.setAttribute('aria-label', service.title);
    cancel.type = 'button'; cancel.textContent = 'Cancel'; accept.type = 'submit';
    accept.textContent = service.kind === 5 ? 'Import' : 'Download';
    form.append(title); if (service.kind === 5) form.append(input);
    form.append(status, cancel, accept); dialog.append(form);
    let settled = false, exportChunks = null;
    const signal = host.signal, capability = host.document.defaultView || globalThis;
    const abort = () => finish('cancelled');
    const finish = (result, value = '', error = '', operation = null) => {
      if (settled) return; settled = true;
      signal?.removeEventListener('abort', abort);
      if (dialog.open) dialog.close(); dialog.remove();
      if (previous?.isConnected) previous.focus({preventScroll: true});
      resolve(operation || {...base, status: result, value, error});
    };
    if (signal?.aborted) { finish('cancelled'); return; }
    signal?.addEventListener('abort', abort, {once: true});
    cancel.addEventListener('click', () => finish('cancelled'));
    dialog.addEventListener('cancel', event => { event.preventDefault(); finish('cancelled'); });
    dialog.addEventListener('close', () => finish('cancelled'));
    dialog.addEventListener('keydown', event => { event.stopPropagation(); });
    form.addEventListener('submit', async event => {
      event.preventDefault(); if (settled || accept.disabled) return;
      accept.disabled = true;
      try {
        if (service.kind === 5) {
          if (service.chunked && host.exchange) {
            const operation = await uploadTextFile(input.files?.[0], service, host.exchange, signal);
            if (!settled) finish('success', '', '', operation);
          } else {
            const value = await readTextFile(input.files?.[0], limit);
            if (!settled) finish('success', value);
          }
        } else {
          // This runs directly from the user's Download action, retaining the
          // browser's user activation requirement even after a delayed poll.
          const urls = host.URL || capability.URL, BlobType = host.Blob || capability.Blob;
          const url = urls.createObjectURL(new BlobType(exportChunks || [service.value], {type: 'text/plain;charset=utf-8'}));
          const link = document.createElement('a'); link.href = url; link.download = 'export.txt';
          try { dialog.append(link); link.click(); }
          finally { link.remove(); (host.setTimeout || capability.setTimeout.bind(capability))(() => urls.revokeObjectURL(url), 1000); }
          finish('success');
        }
      } catch (error) {
        if (!settled) { status.textContent = error.message || 'File content operation failed'; accept.disabled = false; }
      }
    });
    if (service.kind === 6 && service.chunked && host.exchange) {
      // Prefetch bounded chunks before enabling the user's Download action;
      // the eventual link click still executes directly under user activation.
      accept.disabled = true;
      downloadTextFile(service, host.exchange, signal).then(chunks => {
        if (!settled) { exportChunks = chunks; accept.disabled = false; }
      }).catch(error => { if (!settled) finish('error', '', error.message); });
    }
    try { (document.querySelector?.('#stage') || document.body).append(dialog); dialog.showModal(); accept.focus(); }
    catch (error) { finish('error', '', error.message || 'Could not open file dialog'); }
  });
}
