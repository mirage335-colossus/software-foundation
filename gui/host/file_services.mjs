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
    let settled = false;
    const signal = host.signal, capability = host.document.defaultView || globalThis;
    const abort = () => finish('cancelled');
    const finish = (result, value = '', error = '') => {
      if (settled) return; settled = true;
      signal?.removeEventListener('abort', abort);
      if (dialog.open) dialog.close(); dialog.remove();
      if (previous?.isConnected) previous.focus({preventScroll: true});
      resolve({...base, status: result, value, error});
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
          const value = await readTextFile(input.files?.[0], limit);
          if (!settled) finish('success', value);
        } else {
          // This runs directly from the user's Download action, retaining the
          // browser's user activation requirement even after a delayed poll.
          const urls = host.URL || capability.URL, BlobType = host.Blob || capability.Blob;
          const url = urls.createObjectURL(new BlobType([service.value], {type: 'text/plain;charset=utf-8'}));
          const link = document.createElement('a'); link.href = url; link.download = 'export.txt';
          try { dialog.append(link); link.click(); }
          finally { link.remove(); (host.setTimeout || capability.setTimeout.bind(capability))(() => urls.revokeObjectURL(url), 1000); }
          finish('success');
        }
      } catch (error) {
        if (!settled) { status.textContent = error.message || 'File content operation failed'; accept.disabled = false; }
      }
    });
    try { (document.querySelector?.('#stage') || document.body).append(dialog); dialog.showModal(); accept.focus(); }
    catch (error) { finish('error', '', error.message || 'Could not open file dialog'); }
  });
}
