// SPDX-License-Identifier: CC0-1.0
// Pure data validation shared by both sides of the isolated renderer channel.
// Physical listeners and application behavior belong to their respective owners.
const basic = 97n, successor = 8225n, editorFeatures = 8255n, mouseFeature = 8192n, maximum = 18446744073709551615n;
const malformed = () => { throw Error('Invalid browser surface packet'); };
const stale = message => { const error = Error(message); error.stale = true; throw error; };
const profileFeatures = profile => {
  if (profile === 'legacy') return basic;
  if (profile === 'mouse_v1') return successor;
  if (profile === 'editor_v1') return editorFeatures;
  malformed();
};

const record = value => value !== null && typeof value === 'object' && !Array.isArray(value) &&
  [Object.prototype, null].includes(Object.getPrototypeOf(value));
const shape = (value, names) => {
  if (!record(value)) malformed();
  const keys = Reflect.ownKeys(value);
  if (keys.length !== names.length || keys.some(key => {
    const descriptor = Object.getOwnPropertyDescriptor(value, key);
    return !names.includes(key) || !descriptor?.enumerable || !Object.hasOwn(descriptor, 'value');
  })) malformed();
};
const field = (value, name) => {
  if (!record(value)) malformed();
  const descriptor = Object.getOwnPropertyDescriptor(value, name);
  if (!descriptor?.enumerable || !Object.hasOwn(descriptor, 'value')) malformed();
  return descriptor.value;
};
const array = (value, maximumLength, exactLength = null) => {
  if (!Array.isArray(value) || Object.getPrototypeOf(value) !== Array.prototype || value.length > maximumLength ||
      (exactLength !== null && value.length !== exactLength)) malformed();
  const keys = Reflect.ownKeys(value);
  if (keys.length !== value.length + 1) malformed();
  for (let index = 0; index < value.length; ++index) {
    const descriptor = Object.getOwnPropertyDescriptor(value, String(index));
    if (!descriptor?.enumerable || !Object.hasOwn(descriptor, 'value')) malformed();
  }
};
const boolean = value => { if (typeof value !== 'boolean') malformed(); };
const integer = (value, low, high) => {
  if (!Number.isSafeInteger(value) || value < low || value > high) malformed();
};
const finite = value => {
  if (typeof value !== 'number' || !Number.isFinite(value) || Math.abs(value) > 1000000) malformed();
};
const decimal = (value, nonzero = false) => {
  if (typeof value !== 'string' || !/^(0|[1-9][0-9]{0,19})$/.test(value)) malformed();
  const result = BigInt(value);
  if (result > maximum || (nonzero && result === 0n)) malformed();
  return result;
};
const text = (value, maximumBytes, nonempty = false) => {
  if (typeof value !== 'string' || (nonempty && !value.length) || value.length > maximumBytes) malformed();
  let bytes = 0;
  for (const character of value) {
    const point = character.codePointAt(0);
    if (!point || (point >= 0xd800 && point <= 0xdfff)) malformed();
    bytes += point <= 0x7f ? 1 : point <= 0x7ff ? 2 : point <= 0xffff ? 3 : 4;
    if (bytes > maximumBytes) malformed();
  }
};
const range = value => {
  array(value, 2, 2);
  for (const offset of value) integer(offset, 0, 65536);
  if (value[0] > value[1]) malformed();
};
const textRange = (value, surrounding) => {
  range(value);
  const boundaries = new Set([0]);
  let bytes = 0;
  for (const character of surrounding) {
    const point = character.codePointAt(0);
    bytes += point <= 0x7f ? 1 : point <= 0x7ff ? 2 : point <= 0xffff ? 3 : 4;
    boundaries.add(bytes);
  }
  if (!boundaries.has(value[0]) || !boundaries.has(value[1])) malformed();
};
const editorContext = (value, supported, limits) => {
  shape(value, ['revision', 'compositionTransaction', 'surrounding', 'selection', 'selectionBackward', 'caret', 'editable', 'inputPurpose']);
  if (!(supported & 8n)) malformed();
  decimal(value.revision, true);
  const composition = decimal(value.compositionTransaction);
  text(value.surrounding, limits.textBytes); textRange(value.selection, value.surrounding);
  boolean(value.selectionBackward); rect(value.caret); boolean(value.editable); text(value.inputPurpose, 64);
  if (composition && (!(supported & 4n) || !value.editable)) malformed();
};
const keyText = (key, code, wildcard = false) => {
  text(key, 64, !wildcard);
  if (typeof code !== 'string' || code.length > 64 || !/^[\x21-\x7e]*$/.test(code)) malformed();
};
const identity = value => {
  shape(value, ['owner', 'presentationRevision', 'generation', 'epoch', 'context']);
  shape(value.owner, ['id', 'generation']); text(value.owner.id, 128, true); decimal(value.owner.generation, true);
  for (const field of ['presentationRevision', 'generation', 'epoch', 'context']) decimal(value[field], true);
};
const sameOwner = (a, b) => a?.id === b.id && a?.generation === b.generation;
const sameIdentity = (a, b) => sameOwner(a.owner, b.owner) &&
  ['presentationRevision', 'generation', 'epoch', 'context'].every(field => a[field] === b[field]);
const rect = value => {
  array(value, 4, 4); for (const coordinate of value) finite(coordinate);
  if (value[2] < 0 || value[3] < 0) malformed();
};
const sameRect = (a, b) => a.every((value, index) => value === b[index]);
const capabilities = (value, allowed) => {
  const supported = decimal(field(value, 'supported'));
  shape(value, supported & mouseFeature ? ['version', 'supported', 'limits', 'mouseInputVersion'] : ['version', 'supported', 'limits']);
  if (value.version !== 1) malformed();
  if ((supported & ~allowed) || ((supported & mouseFeature) && value.mouseInputVersion !== 1)) malformed();
  const ceilings = {textBytes:65536, clipboardBytes:65536, popupItems:1024, popupTextBytes:65536, captureRules:64, heldKeys:64, popupDepth:8};
  shape(value.limits, Object.keys(ceilings));
  for (const [field, ceiling] of Object.entries(ceilings)) integer(value.limits[field], 1, ceiling);
  return supported;
};
const capture = value => { if (value !== 'pass' && value !== 'capture') malformed(); };
const presentation = (value, snapshot, supported, limits, profile) => {
  shape(value, ['identity', 'required', 'bounds', 'clip', 'displayScale', 'available', 'keys', 'editor', 'clipboard', 'popup']);
  identity(value.identity);
  if (decimal(value.required) & ~supported) malformed();
  rect(value.bounds); rect(value.clip);
  if (value.clip[0] < value.bounds[0] || value.clip[1] < value.bounds[1] ||
      value.clip[0] + value.clip[2] > value.bounds[0] + value.bounds[2] ||
      value.clip[1] + value.clip[3] > value.bounds[1] + value.bounds[3]) malformed();
  if (typeof value.displayScale !== 'number' || !Number.isFinite(value.displayScale) || value.displayScale <= 0 || value.displayScale > 16) malformed();
  boolean(value.available);
  if (profile === 'editor_v1') {
    if (value.editor !== null) editorContext(value.editor, supported, limits);
    if (value.clipboard !== null || value.popup !== null) malformed();
  } else if (value.editor !== null || value.clipboard !== null || value.popup !== null) malformed();
  shape(value.keys, ['fallback', 'rules']); capture(value.keys.fallback); array(value.keys.rules, limits.captureRules);
  if ((value.keys.fallback === 'capture' || value.keys.rules.length) && !(supported & 1n)) malformed();
  for (const rule of value.keys.rules) {
    shape(rule, ['key', 'code', 'requiredModifiers', 'forbiddenModifiers', 'down', 'up', 'disposition']);
    keyText(rule.key, rule.code, true); capture(rule.disposition); boolean(rule.down); boolean(rule.up);
    integer(rule.requiredModifiers, 0, 31); integer(rule.forbiddenModifiers, 0, 31);
    if ((!rule.down && !rule.up) || (rule.requiredModifiers & rule.forbiddenModifiers)) malformed();
  }
  const revision = field(snapshot, 'revision'), closed = field(snapshot, 'closed'), scale = field(snapshot, 'scale');
  decimal(revision); boolean(closed);
  if (value.identity.presentationRevision !== revision || value.displayScale !== scale) malformed();
  const widgets = field(snapshot, 'widgets'); array(widgets, 4096);
  const owners = widgets.filter(widget => {
    const key = field(widget, 'key'); shape(key, ['id', 'generation']);
    return sameOwner(key, value.identity.owner);
  });
  if (owners.length !== 1) malformed();
  if (value.available) {
    const owner = owners[0];
    if (field(owner, 'visible') !== true || field(owner, 'enabled') !== true || field(owner, 'inModal') !== true) malformed();
    const bounds = field(owner, 'bounds'), clip = field(owner, 'clip'); rect(bounds); rect(clip);
    if (!sameRect(value.bounds, bounds) || !sameRect(value.clip, clip)) malformed();
  }
};

export function validateSurfaceState(snapshot, surface, profile = 'legacy') {
  const allowed = profileFeatures(profile);
  if (surface === null) return surface;
  if (profile === 'editor_v1') {
    shape(surface, ['version', 'profile', 'capabilities', 'presentation', 'focused', 'active', 'composition', 'lastSequence', 'serviceActive']);
    if (surface.version !== 2 || surface.profile !== 'editor_v1') malformed();
    if (surface.composition !== null) decimal(surface.composition, true);
  } else {
    shape(surface, ['version', 'capabilities', 'presentation', 'focused', 'active', 'composition', 'lastSequence', 'serviceActive']);
    if (surface.version !== 1 || surface.composition !== null) malformed();
  }
  const supported = capabilities(surface.capabilities, allowed);
  boolean(surface.focused); boolean(surface.active); boolean(surface.serviceActive); decimal(surface.lastSequence);
  if (surface.presentation !== null) presentation(surface.presentation, snapshot, supported, surface.capabilities.limits, profile);
  if (profile === 'editor_v1') {
    const editor = surface.presentation?.editor;
    if (surface.composition !== null && (!(supported & 4n) || !editor?.editable || !surface.presentation.available ||
        !surface.focused || !surface.active || surface.serviceActive)) malformed();
    // Zero attestation is a pending native readback, never proof of continuity.
    if (editor && editor.compositionTransaction !== '0' && editor.compositionTransaction !== surface.composition) malformed();
  }
  return surface;
}

const input = (value, profile) => {
  const kind = field(value, 'kind');
  if (kind === 'key') {
    shape(value, ['kind', 'phase', 'key', 'code', 'location', 'modifiers', 'repeat']);
    if (value.phase !== 'down' && value.phase !== 'up') malformed();
    keyText(value.key, value.code); integer(value.location, 0, 3); integer(value.modifiers, 0, 31); boolean(value.repeat);
    if (value.phase === 'up' && value.repeat) malformed();
    return 1n;
  }
  if (kind === 'focus') {
    shape(value, ['kind', 'focused', 'active', 'cause']); boolean(value.focused); boolean(value.active);
    if (value.cause !== 'direct' && value.cause !== 'external') malformed();
    return 32n;
  }
  if (kind === 'pointer' && profile === 'legacy') {
    shape(value, ['kind', 'phase', 'pointer', 'x', 'y', 'wheelX', 'wheelY', 'button', 'buttons', 'clicks', 'modifiers']);
    if (!['move', 'down', 'up', 'cancel', 'wheel', 'context'].includes(value.phase)) malformed();
    const pointer = decimal(value.pointer);
    for (const field of ['x', 'y', 'wheelX', 'wheelY']) finite(value[field]);
    integer(value.button, 0, 4); integer(value.buttons, 0, 31); integer(value.clicks, 1, 3); integer(value.modifiers, 0, 31);
    if (['down', 'up', 'cancel'].includes(value.phase) && !pointer) malformed();
    if (value.phase === 'wheel' ? !value.wheelX && !value.wheelY : value.wheelX || value.wheelY) malformed();
    return 64n;
  }
  if (kind === 'mouse' && (profile === 'mouse_v1' || profile === 'editor_v1')) {
    shape(value, ['kind', 'version', 'phase', 'captureToken', 'x', 'y', 'wheelX', 'wheelY', 'button', 'buttons', 'clicks', 'modifiers', 'contextOrigin']);
    if (value.version !== 1 || !['move', 'down', 'up', 'wheel', 'cancel', 'context'].includes(value.phase)) malformed();
    const token = decimal(value.captureToken);
    for (const field of ['x', 'y', 'wheelX', 'wheelY']) finite(value[field]);
    integer(value.button, 0, 4); integer(value.buttons, 0, 31); integer(value.clicks, 0, 3); integer(value.modifiers, 0, 31);
    if (value.contextOrigin !== 'pointer' && value.contextOrigin !== 'keyboard') malformed();
    if (value.phase === 'down' || value.phase === 'up') {
      if (!token || Boolean(value.buttons & [1, 4, 2, 8, 16][value.button]) !== (value.phase === 'down')) malformed();
    } else if (value.button || value.clicks) malformed();
    if (value.phase === 'wheel' ? (!value.wheelX && !value.wheelY) || Math.fround(value.wheelX) !== value.wheelX ||
        Math.fround(value.wheelY) !== value.wheelY : value.wheelX || value.wheelY) malformed();
    if (value.phase === 'cancel') {
      if (!token || value.x || value.y || value.buttons || value.modifiers) malformed();
    } else if (!token && value.buttons) malformed();
    if (value.contextOrigin === 'keyboard' && (value.phase !== 'context' || value.x || value.y || value.modifiers)) malformed();
    return mouseFeature;
  }
  if (profile === 'editor_v1') {
    if (kind === 'text') {
      shape(value, ['kind', 'transaction', 'editorRevision', 'text', 'replacement']);
      decimal(value.transaction, true); decimal(value.editorRevision, true); text(value.text, 65536);
      if (value.replacement !== null) range(value.replacement);
      if (value.text === '' && value.replacement !== null && value.replacement[0] === value.replacement[1]) malformed();
      return 2n;
    }
    if (kind === 'composition') {
      shape(value, ['kind', 'operation', 'transaction', 'editorRevision', 'text', 'selection', 'replacement']);
      if (!['begin', 'update', 'commit', 'cancel'].includes(value.operation)) malformed();
      decimal(value.transaction, true); decimal(value.editorRevision, true); text(value.text, 65536);
      textRange(value.selection, value.text);
      if (value.replacement !== null) {
        if (value.operation !== 'begin') malformed();
        range(value.replacement);
      }
      if (value.operation === 'cancel' && (value.text !== '' || value.selection[0] || value.selection[1])) malformed();
      return 4n;
    }
    if (kind === 'selection') {
      shape(value, ['kind', 'editorRevision', 'selection', 'backward']);
      decimal(value.editorRevision, true); range(value.selection); boolean(value.backward);
      return 16n;
    }
  }
  malformed();
};

export function validateSurfaceOperation(operation, snapshot, surface, profile = 'legacy') {
  const allowed = profileFeatures(profile);
  const type = field(operation, 'type');
  if (type === 'surfaceConnect') {
    const supported = decimal(field(operation, 'supported'));
    if (profile === 'editor_v1') {
      shape(operation, supported & mouseFeature ? ['type', 'version', 'profile', 'supported', 'mouseInputVersion'] : ['type', 'version', 'profile', 'supported']);
      if (operation.version !== 2 || operation.profile !== 'editor_v1') malformed();
    } else {
      shape(operation, supported & mouseFeature ? ['type', 'version', 'supported', 'mouseInputVersion'] : ['type', 'version', 'supported']);
      if (operation.version !== 1) malformed();
    }
    if ((supported & ~allowed) ||
        ((supported & mouseFeature) && operation.mouseInputVersion !== 1)) malformed();
    validateSurfaceState(snapshot, surface, profile);
    const closed = snapshot === null ? false : field(snapshot, 'closed'); boolean(closed);
    if (surface !== null || closed) stale('Surface connection is no longer available');
    return operation;
  }
  if (type !== 'surfaceInput') malformed();
  shape(operation, ['type', 'identity', 'sequence', 'input']); identity(operation.identity);
  const sequence = decimal(operation.sequence, true), required = input(operation.input, profile);
  validateSurfaceState(snapshot, surface, profile);
  if (!surface?.presentation || !snapshot) stale('Surface is no longer available');
  const closed = field(snapshot, 'closed'); boolean(closed);
  if (closed) stale('Surface is no longer available');
  if (!sameIdentity(operation.identity, surface.presentation.identity)) stale('Surface identity was replaced');
  if (sequence <= BigInt(surface.lastSequence)) stale('Surface operation was already consumed');
  if (surface.serviceActive) stale('A host service owns input');
  if (!(BigInt(surface.capabilities.supported) & required)) stale('Surface capability is unavailable');
  if (operation.input.kind !== 'focus') {
    if (!surface.presentation.available || !surface.active) stale('Surface is unavailable or inactive');
    if (operation.input.kind === 'key' && !surface.focused) stale('Surface is not focused');
  }
  if (profile === 'editor_v1' && ['text', 'composition', 'selection'].includes(operation.input.kind)) {
    const value = operation.input, editor = surface.presentation.editor;
    if (!surface.focused) stale('Surface is not focused');
    if (!editor || value.editorRevision !== editor.revision) stale('Editor revision was replaced');
    if (value.kind !== 'selection' && !editor.editable) stale('Editor is not editable');
    if (value.kind !== 'selection') text(value.text, surface.capabilities.limits.textBytes);
    if (value.kind === 'selection') textRange(value.selection, editor.surrounding);
    else if (value.replacement !== null) textRange(value.replacement, editor.surrounding);
    if (value.kind === 'text') {
      if (surface.composition !== null) stale('A composition owns input');
      const replaced = value.replacement ?? editor.selection;
      if (value.text === '' && replaced[0] === replaced[1]) malformed();
    } else if (value.kind === 'composition') {
      if (value.operation === 'begin' ? surface.composition !== null : surface.composition !== value.transaction)
        stale('Composition transaction was replaced');
    }
  }
  return operation;
}
