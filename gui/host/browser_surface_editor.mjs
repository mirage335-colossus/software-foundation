import {surfaceScalarMap} from './browser_surface.mjs';
import {captureEditorText, proveEditorReplacement, proveEditorCompositionPassage} from './browser_surface_editor_text.mjs';
import {createEditorObservationController} from './browser_surface_editor_controller.mjs';

const maximum = 18446744073709551615n;
const modifiers = event => (event.shiftKey ? 1 : 0) | (event.ctrlKey ? 2 : 0) | (event.altKey ? 4 : 0) |
  (event.metaKey ? 8 : 0) | (event.getModifierState?.('AltGraph') ? 16 : 0);
const same = (a, b) => a?.value === b?.value && a?.selectionStart === b?.selectionStart &&
  a?.selectionEnd === b?.selectionEnd && (a?.selectionDirection === 'backward') === (b?.selectionDirection === 'backward');

// Additive, unselected physical editor implementation. The sender implements the
// private checked observation contract, not the existing surfaceInput protocol.
export function createBrowserEditorConduit({root, document = globalThis.document, send,
  onFailure = () => {}, onResync = () => {}, onRevoke = () => {}, onTrace = () => {},
  maxPending = 64, maxBytes = 1048576} = {}) {
  if (!root || !document || typeof document.createElement !== 'function' ||
      ![onFailure, onResync, onRevoke, onTrace].every(value => typeof value === 'function')) throw Error('Invalid editor conduit');
  let node = null, listeners = [], basis = null, settings = null, live = false, closed = false,
    incarnation = 0n, serial = 0n, candidate = null, pending = null, composition = null, terminal = null,
    watermark = null, last = null, revoking = false, deadGroups = [], publication = 0n, pausedCapture = null, pendingFocus = null;
  const held = new Map();
  const callback = (fn, ...args) => { try { fn(...args); } catch (error) { fail(error); } };
  const trace = (type, data = {}) => { if (!closed) callback(onTrace, Object.freeze({type, incarnation: String(incarnation), ...data})); };
  const remove = () => {
    for (const [target, type, fn] of listeners) target.removeEventListener(type, fn, true);
    listeners = []; const old = node; node = null; old?.remove();
  };
  const revoke = (reason, notifyOwner = true, preserveFocus = false) => {
    if (revoking) return;
    revoking = true; const wasLive = live, oldComposition = composition?.transaction ?? null;
    const keys = [...held.values()].map(value => ({...value}));
    const focus = preserveFocus && pendingFocus?.ticket === publication ? pendingFocus : null;
    live = false; candidate = pending = composition = terminal = pausedCapture = null; deadGroups = []; held.clear(); remove();
    if (focus) focus.origin = document.activeElement;
    else pendingFocus = null;
    if (wasLive && notifyOwner) callback(onRevoke, Object.freeze({reason, basis, composition: oldComposition,
      keys: Object.freeze(keys), incarnation: String(incarnation)}));
    revoking = false;
  };
  const resync = reason => { controller.retire(reason); };
  const fail = error => { if (!closed) { closed = true; pendingFocus = null; ++publication; controller?.close(); revoke('Editor failure', false); try { onFailure(error); } catch {} } };
  const next = () => { if (serial === maximum) throw Error('Native editor passage exhausted'); return String(++serial); };
  const read = () => captureEditorText({value: node.value, selectionStart: node.selectionStart,
    selectionEnd: node.selectionEnd, selectionDirection: node.selectionDirection});
  const position = options => {
    if (!node || !options.caret) return;
    const [x, y, width, height] = options.caret;
    if (![x, y, width, height].every(value => Number.isFinite(value) && Math.abs(value) <= 1000000) || width < 0 || height < 0) throw Error('Invalid editor caret');
    const box = root.getBoundingClientRect(), clip = options.clip ?? [0, 0, box.width, box.height];
    if (!Array.isArray(clip) || clip.length !== 4 || !clip.every(Number.isFinite) || clip[2] < 1 || clip[3] < 1) throw Error('Invalid editor clip');
    node.style.left = `${box.left + Math.max(clip[0], Math.min(x, clip[0] + clip[2] - 1))}px`;
    node.style.top = `${box.top + Math.max(clip[1], Math.min(y, clip[1] + clip[3] - 1))}px`;
  };
  const trusted = event => !closed && live && node && event.isTrusted === true && event.target === node &&
    document.activeElement === node && !settings?.serviceActive && settings?.active !== false;
  const guard = fn => event => {
    if (!trusted(event)) return;
    try {
      if (controller.state().paused) {
        event.stopImmediatePropagation?.(); if (event.cancelable) event.preventDefault();
        const changed = !same(read(), pausedCapture);
        const data = event.type === 'keyup' ? copyKey(event) : null;
        const ownedRelease = data && held.has(JSON.stringify([data.code || data.key, data.location]));
        const phase = ['compositionstart', 'compositionupdate', 'compositionend'].includes(event.type);
        const unblockable = !event.cancelable && ['keydown', 'beforeinput', 'paste', 'drop', 'cut', 'pointerdown'].includes(event.type);
        if (changed || ownedRelease || phase || unblockable) resync(`Paused editor ${changed ? 'capture changed' : unblockable ? 'unblockable input' : 'ambiguous native phase'}`);
        return;
      }
      fn(event);
    } catch (error) { resync(error.message); }
  };
  const observe = (kind, authority, before, after, data, {group = null, groupEnd = false, transaction = '0'} = {}) =>
    controller.observe({kind, authority, before, after, data, group, groupEnd, transaction});
  const terminalPassage = (phase, event, capture) => terminal && !candidate && event.data === terminal.text &&
    same(capture, terminal.after) && (event.inputType === 'insertFromComposition' ||
      (phase === 'input' && event.inputType === 'insertCompositionText' && event.isComposing === false));
  const copyKey = event => {
    if (typeof event.key !== 'string' || !event.key || event.key.length > 64 || typeof event.code !== 'string' ||
        !/^[\x21-\x7e]*$/.test(event.code) || event.code.length > 64 || !Number.isInteger(event.location) ||
        event.location < 0 || event.location > 3) throw Error('Invalid native editor key');
    captureEditorText({value: event.key, selectionStart: 0, selectionEnd: 0, selectionDirection: 'none'}, 64);
    return {phase: event.type === 'keyup' ? 'up' : 'down', key: event.key, code: event.code,
      location: event.location, modifiers: modifiers(event), repeat: !!event.repeat, isComposing: !!event.isComposing};
  };
  const key = event => {
    if (event.defaultPrevented) { resync('Native editor key was already cancelled'); return; }
    const data = copyKey(event), keyId = JSON.stringify([data.code || data.key, data.location]);
    const before = read(), altGraph = Boolean(data.modifiers & 16), command = Boolean(data.modifiers & (2 | 8)) && !altGraph;
    let entry = held.get(keyId), group = null, groupEnd = false, zeroEdit = false;
    if (data.phase === 'up') {
      if (!entry) return;
      held.delete(keyId); group = entry.group; groupEnd = true; data.repeat = false;
      if (candidate?.keyId === keyId) {
        if (candidate.dead) {
          if (deadGroups.length >= 7) { resync('Native dead-key prefix limit'); return; }
          deadGroups.push(group); groupEnd = false;
        } else zeroEdit = true;
        candidate = null;
      }
    } else {
      if ((entry && !data.repeat) || (!entry && data.repeat) || (!entry && held.size >= 64)) { resync('Invalid held editor key'); return; }
      const textKey = !command && (data.key === 'Dead' || data.key === 'Process' || data.key === 'Unidentified' ||
        [...data.key].length === 1);
      if (!composition && deadGroups.length && !textKey) { resync('Native dead-key prefix interrupted'); return; }
      if (!composition && textKey) {
        if (candidate || pending) { resync('Overlapping native key passage'); return; }
        group = next(); candidate = {group, keyId, before, dead: data.key === 'Dead'}; terminal = null;
      }
      entry = {...data, group}; held.set(keyId, entry);
      if (composition && data.key === 'Escape') composition.cancelRequested = true;
      // Native engine key defaults own these operations. In particular a host
      // Backspace/Enter must never also become a textarea text observation.
      if (!composition && (!textKey || command)) event.preventDefault();
    }
    event.stopImmediatePropagation?.();
    if (!observe('key', 'native', before, before, data, {group, groupEnd})) return;
    if (zeroEdit) trace('zero-edit-group', {group});
    trace('key', {phase: data.phase, group});
  };
  const beforeInput = event => {
    if (event.defaultPrevented) { resync('Native editor input was already cancelled'); return; }
    const before = read(), inputType = event.inputType;
    if (terminalPassage('beforeinput', event, before)) {
      if (terminal.beforeConsumed) { resync('Duplicate terminal beforeinput'); return; }
      terminal.beforeConsumed = true; if (event.cancelable) event.preventDefault(); trace('terminal-beforeinput'); return;
    }
    if (pending) { resync('Unmatched native beforeinput'); return; }
    if (composition) {
      if (inputType !== 'insertCompositionText') { resync('Unsupported native composition intent'); return; }
      if (event.data !== null) captureEditorText({value: event.data, selectionStart: 0, selectionEnd: 0, selectionDirection: 'none'});
      pending = {before, inputType, transaction: composition.transaction}; return;
    }
    if (!['insertText', 'insertReplacementText'].includes(inputType) || event.isComposing || typeof event.data !== 'string') {
      if (event.cancelable) event.preventDefault(); resync('Unsupported native editor intent'); return;
    }
    // dom-text-pair-v1 is a positive event grammar. No timer, microtask or
    // "last key" timestamp grants a group, and unknown extra passages retire.
    if (!candidate && (held.size || deadGroups.length)) { if (event.cancelable) event.preventDefault(); resync('Ambiguous native input source'); return; }
    captureEditorText({value: event.data, selectionStart: 0, selectionEnd: 0, selectionDirection: 'none'});
    pending = {before, inputType, data: event.data, group: candidate?.group ?? null,
      sourceGroups: candidate ? [...deadGroups, candidate.group] : null};
  };
  const input = event => {
    const after = read();
    if (terminalPassage('input', event, after)) {
      if (terminal.inputConsumed) { resync('Duplicate terminal input'); return; }
      terminal.inputConsumed = true; trace('terminal-input'); return;
    }
    if (composition) {
      if (event.inputType !== 'insertCompositionText' || (!pending && composition.pendingData === null)) { resync('Unmatched native composition input'); return; }
      const captured = pending?.before ?? composition.last;
      if (pending && pending.transaction !== composition.transaction) { resync('Replaced native composition passage'); return; }
      const proof = proveEditorCompositionPassage(composition.root, after);
      if (!proof || (typeof event.data === 'string' && event.data !== proof.text) ||
          (composition.pendingData !== null && composition.pendingData !== proof.text)) { resync('Unproved native preedit passage'); return; }
      const active = composition;
      if (!observe('composition', 'composition', captured, after, {operation: 'update', text: proof.text, selection: proof.selection},
        {transaction: active.transaction}) || composition !== active) return;
      composition.last = after; composition.seenInput = true; composition.pendingData = null; pending = null; last = watermark = after;
      trace('composition-input', {transaction: composition.transaction}); return;
    }
    if (!pending || !['insertText', 'insertReplacementText'].includes(event.inputType) || event.inputType !== pending.inputType ||
        event.isComposing || (typeof event.data === 'string' && event.data !== pending.data)) { resync('Unmatched native input'); return; }
    const captured = pending, proof = proveEditorReplacement(captured.before, after, {data: captured.data});
    if (!proof) { resync('Unproved native replacement'); return; }
    pending = null; candidate = null; terminal = null; deadGroups = []; last = watermark = after;
    if (!observe('text', captured.group ? 'default' : 'range', captured.before, after,
      {inputType: captured.inputType, text: proof.text, replacement: proof.replacement,
        ...(captured.sourceGroups ? {sourceGroups: captured.sourceGroups} : {})}, {group: captured.group, groupEnd: true})) return;
    trace('text-input', {group: captured.group});
  };
  const compositionStart = event => {
    if (composition || pending || (held.size && !candidate) || event.defaultPrevented) { resync('Ambiguous native composition start'); return; }
    const before = read(), transaction = next(), group = candidate?.group ?? deadGroups.at(-1) ?? null;
    const sourceGroups = group ? [...deadGroups, ...(candidate ? [candidate.group] : [])] : null;
    composition = {transaction, root: before, last: before, pendingData: null, seenInput: false, cancelRequested: false};
    candidate = null; terminal = null; deadGroups = [];
    const active = composition;
    if (!observe('composition', group ? 'default' : 'range', before, before,
      {operation: 'begin', text: '', selection: [0, 0], replacement: before.selection,
        ...(sourceGroups ? {sourceGroups} : {})}, {transaction, group, groupEnd: true}) || composition !== active) return;
    trace('composition-start', {transaction});
  };
  const compositionUpdate = event => {
    if (!composition || typeof event.data !== 'string') { resync('Unmatched composition update'); return; }
    captureEditorText({value: event.data, selectionStart: 0, selectionEnd: 0, selectionDirection: 'none'});
    composition.pendingData = event.data; trace('composition-update', {transaction: composition.transaction});
  };
  const compositionEnd = event => {
    if (!composition || pending) { resync('Unmatched composition ending'); return; }
    const active = composition, after = read(), proof = proveEditorCompositionPassage(active.root, after);
    if (typeof event.data !== 'string' || !proof || (event.data && event.data !== proof.text)) { resync('Unproved composition ending'); return; }
    const operation = event.data ? 'commit' : active.cancelRequested ? 'cancel' : null;
    if (!operation) { resync('Ambiguous empty composition ending'); return; }
    const data = operation === 'cancel' ? {operation, text: '', selection: [0, 0]} :
      {operation, text: proof.text, selection: proof.selection};
    if (!observe('composition', 'composition', active.last, after, data, {transaction: active.transaction}) || composition !== active) return;
    composition = null; terminal = {text: proof.text, after, beforeConsumed: false, inputConsumed: false}; last = watermark = after;
    trace('composition-end', {transaction: active.transaction, operation});
  };
  const selection = () => {
    const after = read();
    if (same(after, watermark) || pending || composition) return;
    if (!last || after.value !== last.value || candidate) { resync('Ambiguous native selection change'); return; }
    const before = last; last = watermark = after;
    if (!observe('selection', 'range', before, after, {selection: after.selection, backward: after.selectionDirection === 'backward'})) return;
    trace('selection');
  };
  const create = current => {
    if (incarnation === maximum) throw Error('Native editor incarnation exhausted');
    ++incarnation; node = document.createElement('textarea');
    node.setAttribute('aria-label', 'Application text input'); node.setAttribute('autocomplete', 'off');
    node.spellcheck = false; node.tabIndex = 0;
    Object.assign(node.style, {position: 'fixed', opacity: '0.01', width: '1px', height: '1em',
      overflow: 'hidden', resize: 'none', pointerEvents: 'none'});
    const created = node; root.appendChild(created);
    if (!current() || node !== created) { created.remove(); return false; }
    const listen = (type, fn) => { const wrapped = guard(fn); node.addEventListener(type, wrapped, true); listeners.push([node, type, wrapped]); };
    for (const type of ['keydown', 'keyup']) listen(type, key);
    listen('beforeinput', beforeInput); listen('input', input);
    listen('compositionstart', compositionStart); listen('compositionupdate', compositionUpdate); listen('compositionend', compositionEnd);
    listen('selectionchange', selection);
    for (const type of ['paste', 'drop', 'cut']) listen(type, event => { if (event.cancelable) event.preventDefault(); resync(`Unsupported ${type}`); });
    listen('pointerdown', () => { candidate = terminal = null; if (pending) resync('Pointer interrupted native passage'); });
    const blur = event => { if (!closed && live && event.isTrusted === true && event.target === node) resync('Native editor lost focus'); };
    node.addEventListener('blur', blur, true); listeners.push([node, 'blur', blur]);
    return true;
  };
  const controller = createEditorObservationController({send, maxPending, maxBytes,
    onFailure: error => fail(error),
    onResync: (reason, accepted, metadata) => {
      pendingFocus = null;
      const ticket = publication, state = controller.state(); revoke(reason);
      if (!closed && publication === ticket && controller.state().transition === state.transition &&
          controller.state().session === state.session) {
        if (accepted === null) basis = null;
        callback(onResync, reason, accepted, metadata);
      }
    },
    onBasis: (accepted, meta) => {
      const ticket = publication, state = controller.state();
      const current = () => !closed && publication === ticket && controller.state().session === state.session &&
        controller.state().transition === state.transition && controller.state().basis === accepted;
      if (state.paused && node) {
        try { if (!same(read(), pausedCapture)) throw Error('Paused editor capture changed before owner settlement'); }
        catch (error) { resync(error.message); return; }
      }
      if (meta.settled && composition && !meta.preservePassage) { resync('Native composition authority ended'); return; }
      if (!meta.settled) { revoke('Editor publication replaced', true, true); if (!current() || !create(current)) return; }
      if (!current()) return;
      basis = accepted;
      if (!node) return;
      if (!meta.preservePassage) {
        const map = surfaceScalarMap(accepted.surrounding);
        node.value = accepted.surrounding;
        if (!current()) return;
        node.setSelectionRange(map.utf16Offset(accepted.selection[0]), map.utf16Offset(accepted.selection[1]), accepted.backward ? 'backward' : 'forward');
        if (!current()) return;
        last = watermark = read();
        if (node.value !== accepted.surrounding || JSON.stringify(last.selection) !== JSON.stringify(accepted.selection) ||
            (last.selectionDirection === 'backward') !== accepted.backward) { resync('Native editor projection did not round-trip'); return; }
      }
      if (current()) { live = true; if (controller.state().paused) pausedCapture = read(); }
    }
  });
  return Object.freeze({
    publish(value, options = {}) {
      if (closed || controller.state().paused) return false;
      if (publication === maximum) { fail(Error('Editor publication exhausted')); return false; }
      const ticket = ++publication;
      settings = {...options};
      if (options.editable === false || options.focused === false || options.active === false || options.serviceActive || options.available === false) {
        resync('Editor publication unavailable'); return false;
      }
      pendingFocus = {ticket, origin: document.activeElement};
      try {
        const accepted = controller.activate(value);
        if (!accepted || closed || publication !== ticket || !live || !node || controller.state().paused) return false;
        position(options);
        if (closed || publication !== ticket || !live || !node || controller.state().paused) return false;
        if (document.activeElement !== node && document.activeElement !== pendingFocus?.origin)
          throw Error('Editor focus changed during publication');
        node.focus({preventScroll: true});
        const current = !closed && publication === ticket && live && !controller.state().paused;
        if (current) pendingFocus = null;
        return current;
      } catch (error) { resync(error.message); return false; }
    },
    pause() {
      const state = controller.state(), ticket = publication, current = node;
      if (closed || !['ready', 'awaiting'].includes(state.status) || !state.basis) return false;
      try {
        const captured = node ? read() : null;
        if (closed || publication !== ticket || node !== current || controller.state().session !== state.session) return false;
        if (state.paused && live && node && !same(captured, pausedCapture)) throw Error('Paused editor capture changed');
        if (!controller.pause()) return false;
        pausedCapture = captured; return true;
      } catch (error) { resync(error.message); return false; }
    },
    resume(value, options = {}) {
      if (closed || !live || !node) return false;
      const ticket = publication, target = node, session = controller.state().session;
      const current = () => !closed && publication === ticket && node === target && controller.state().session === session;
      const focus = pendingFocus?.ticket === ticket ? pendingFocus : null;
      try {
        const nextSettings = {...settings, ...options};
        if (!current()) return false;
        if ((document.activeElement !== node && (!focus || document.activeElement !== focus.origin)) ||
            nextSettings.editable === false || nextSettings.focused === false ||
            nextSettings.active === false || nextSettings.serviceActive || nextSettings.available === false)
          throw Error('Paused editor eligibility changed');
        if (controller.state().paused && !same(read(), pausedCapture)) throw Error('Paused editor capture changed');
        if (!controller.resume(value)) throw Error('Paused editor projection changed');
        settings = nextSettings; pausedCapture = null; position(settings);
        if (!current() || !live || controller.state().paused) return false;
        if (document.activeElement !== node) {
          if (!focus || pendingFocus !== focus || document.activeElement !== focus.origin)
            throw Error('Paused editor eligibility changed');
          node.focus({preventScroll: true});
        }
        const resumed = current() && live && !controller.state().paused && document.activeElement === node;
        if (resumed) pendingFocus = null;
        return resumed;
      } catch (error) { if (current()) resync(error.message); return false; }
    },
    retire: reason => resync(reason ?? 'Editor retired'),
    close() { if (!closed) { closed = true; pendingFocus = null; ++publication; controller.close(); revoke('Editor closed'); } },
    element: () => node,
    state: () => controller.state()
  });
}
