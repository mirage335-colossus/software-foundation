// SPDX-License-Identifier: CC0-1.0
// Model evidence only: the same fake event traverses ancestor capture before
// textarea listeners. No browser, native IME, engine or ABI executes here.
import assert from 'node:assert/strict';
import test from 'node:test';
import {createBrowserSurface} from '../host/browser_surface.mjs';
import {createBrowserEditorSurface} from '../host/browser_surface_editor_integration.mjs';
import {validateSurfaceOperation} from '../host/browser_surface_protocol.mjs';

const wide = '9007199254740993', encoder = new TextEncoder();
const bytes = text => encoder.encode(text).length;
const flush = () => new Promise(resolve => setImmediate(resolve));
const clone = value => structuredClone(value);
const context = basis => JSON.stringify([basis.identity.owner, basis.identity.generation, basis.identity.epoch, basis.identity.context]);
const utf16 = (value, boundary) => {
  let offset = 0, total = 0;
  for (const character of value) { if (total === boundary) break; offset += character.length; total += bytes(character); }
  assert.equal(total, boundary); return offset;
};

class Target {
  listeners = new Map();
  addEventListener(type, fn, options = false) {
    const entries = this.listeners.get(type) ?? [];
    entries.push({fn, capture: options === true || options?.capture === true, once: options?.once === true});
    this.listeners.set(type, entries);
  }
  removeEventListener(type, fn, options = false) {
    const capture = options === true || options?.capture === true;
    this.listeners.set(type, (this.listeners.get(type) ?? []).filter(entry => entry.fn !== fn || entry.capture !== capture));
  }
  dispatch(type, values = {}) {
    const event = {type, target: this, isTrusted: true, cancelable: true, defaultPrevented: false,
      bubbles: !['blur', 'focus', 'pagehide'].includes(type),
      isComposing: false, key: '', code: '', location: 0, repeat: false,
      shiftKey: false, ctrlKey: false, altKey: false, metaKey: false, getModifierState: () => false,
      preventDefault() { if (this.cancelable) this.defaultPrevented = true; },
      stopPropagation() { this.propagationStopped = true; },
      stopImmediatePropagation() { this.immediateStopped = this.propagationStopped = true; }, ...values};
    const path = []; for (let current = this; current; current = current.parent) path.push(current);
    const invoke = (target, capture) => {
      event.currentTarget = target;
      for (const entry of [...(target.listeners.get(type) ?? [])]) {
        if (entry.capture !== capture) continue;
        if (entry.once) target.removeEventListener(type, entry.fn, {capture});
        entry.fn(event); if (event.immediateStopped) return;
      }
    };
    for (const target of [...path].reverse()) { invoke(target, true); if (event.propagationStopped) return event; }
    for (const target of event.bubbles ? path : path.slice(0, 1)) { invoke(target, false); if (event.propagationStopped) return event; }
    return event;
  }
  contains(value) { for (let current = value; current; current = current.parent) if (current === this) return true; return false; }
  listenerCount() { return [...this.listeners.values()].reduce((count, entries) => count + entries.length, 0); }
  focus() {
    const document = this.document;
    if (document.activeElement === this) return;
    const previous = document.activeElement;
    document.activeElement = this;
    previous?.dispatch('blur', {cancelable: false}); previous?.dispatch('focusout', {cancelable: false});
    this.dispatch('focusin', {cancelable: false});
  }
}

class Textarea extends Target {
  constructor(document) {
    super(); this.document = document; this.tagName = 'TEXTAREA'; this.style = {}; this.attributes = new Map();
    this._value = ''; this.selectionStart = this.selectionEnd = 0; this.selectionDirection = 'none';
  }
  setAttribute(name, value) { this.attributes.set(name, value); }
  get value() { return this._value; }
  set value(value) {
    const normalized = value.replace(/\r\n?/g, '\n'); if (normalized === this._value) return;
    this._value = normalized; this.selectionStart = this.selectionEnd = normalized.length;
    this.selectionDirection = 'none'; this.document.selectionTasks.add(this);
  }
  setSelectionRange(first, last, direction = 'none') {
    first = Math.min(this.value.length, Math.max(0, first)); last = Math.min(this.value.length, Math.max(0, last));
    if (last <= first) first = last;
    const nextDirection = ['forward', 'backward'].includes(direction) ? direction : 'none';
    if (this.selectionStart !== first || this.selectionEnd !== last || this.selectionDirection !== nextDirection) this.document.selectionTasks.add(this);
    this.selectionStart = first; this.selectionEnd = last; this.selectionDirection = nextDirection;
  }
  remove() {
    const index = this.parent?.children.indexOf(this) ?? -1;
    if (index >= 0) this.parent.children.splice(index, 1);
    this.parent = null; if (this.document.activeElement === this) this.document.activeElement = null;
  }
}

function frame({value = '', first = value.length, last = first, backward = false, context = '13',
  revision = wide, token = '9007199254741001', focused = true, active = true, serviceActive = false,
  available = true, editable = true, supported = '63', composition = '0', policyComposition = composition === '0' ? null : composition} = {}) {
  const identity = {owner: {id: 'surface', generation: wide}, presentationRevision: wide,
    generation: '7', epoch: '11', context};
  const selection = [bytes(value.slice(0, first)), bytes(value.slice(0, last))];
  const snapshot = {revision: wide, scale: 1, closed: false, widgets: [{key: clone(identity.owner),
    visible: true, enabled: true, inModal: true, bounds: [0, 0, 100, 100], clip: [0, 0, 100, 100]}]};
  const state = {version: 2, profile: 'editor_v1', capabilities: {version: 1, supported,
    limits: {textBytes: 65536, clipboardBytes: 65536, popupItems: 1024, popupTextBytes: 65536, captureRules: 64, heldKeys: 64, popupDepth: 8}},
    presentation: {identity, required: supported, bounds: [0, 0, 100, 100], clip: [0, 0, 100, 100], displayScale: 1, available,
      keys: {fallback: 'pass', rules: []}, editor: {revision, compositionTransaction: composition, surrounding: value,
        selection, selectionBackward: backward, caret: [3, 4, 1, 15], editable, inputPurpose: 'normal'}, clipboard: null, popup: null},
    focused, active, composition: policyComposition, lastSequence: '0', serviceActive};
  if (BigInt(supported) & 8192n) state.capabilities.mouseInputVersion = 1;
  const basis = {token, editorRevision: revision, surrounding: value, selection: clone(selection), backward,
    composition, identity: clone(identity)};
  return {snapshot, state, basis};
}

function fixture(options = {}) {
  const host = new Target(); host.PointerEvent = class {};
  const document = new Target(); document.parent = host; document.defaultView = host;
  document.visibilityState = 'visible'; document.selectionTasks = new Set();
  document.createElement = name => { assert.equal(name, 'textarea'); return new Textarea(document); };
  document.flushSelection = () => { const nodes = [...document.selectionTasks]; document.selectionTasks.clear();
    for (const node of nodes) node.dispatch('selectionchange', {cancelable: false}); };
  const root = new Target(); root.parent = document; root.document = document; root.children = []; root.captured = new Set();
  root.appendChild = node => { node.parent = root; root.children.push(node); options.onAppend?.(node); };
  root.getBoundingClientRect = () => ({left: 10, top: 20, width: 100, height: 100});
  root.setPointerCapture = id => root.captured.add(id);
  root.releasePointerCapture = id => { root.captured.delete(id); root.dispatch('lostpointercapture', {pointerId: id}); };
  document.activeElement = root;
  const operations = [], sent = [], deferred = [], errors = [], revoked = [], resync = [], traces = [], owners = new Map(), compositions = new Map(), captureEvents = [];
  document.addEventListener('keydown', event => captureEvents.push(event), true);
  const initial = options.initial ?? frame(), bases = new Map(), key = state => JSON.stringify([state.presentation?.identity, state.presentation?.editor?.revision]);
  const defaultResolver = (snapshot, state) => bases.get(key(state)) ?? null;
  let acceptedFrame = initial, acknowledge, resolver = options.resolveBasis ?? defaultResolver, receiptSerial = 0n;
  const register = (next, settlement = null) => bases.set(key(next.state), {basis: clone(next.basis), settlement: clone(settlement)}); register(initial);
  const editor = {resolveBasis: (snapshot, state) => resolver(snapshot, state),
    sendObservation(packet) { sent.push(packet); if (!owners.has(packet.session)) owners.set(packet.session, packet.basis);
      return new Promise((resolve, reject) => deferred.push({resolve, reject})); },
    revoke(record) { revoked.push(record); options.onRevoke?.(record); },
    resync(reason, basis, metadata) { resync.push({reason, basis}); options.onResync?.(reason, basis, metadata); }, trace: value => traces.push(value)};
  const surface = createBrowserEditorSurface({root, document, editor,
    resolveOwner: (owner, event) => { options.onResolveOwner?.(owner, event); return owner.id === 'surface' && owner.generation === wide && !event?.blocked ? root : null; },
    send(operation) { operations.push(operation); options.onOperation?.(operation);
      if (operation.type === 'surfaceConnect') return new Promise(resolve => { acknowledge = resolve; });
      return Promise.resolve({}); }, onFailure: error => { errors.push(error); options.onFailure?.(error); },
    ...(options.classifyContext ? {classifyContext: options.classifyContext} : {})});
  const publish = (next, settlement = null) => { register(next, settlement); acceptedFrame = next; surface.accept(next.snapshot, next.state); };
  const answer = async (index, changes = {}) => {
    assert.ok(sent[index], `Expected private observation ${index}`);
    const packet = sent[index], observation = packet.observation, owner = owners.get(packet.session);
    const {publication = 'before', policyComposition, ...receiptChanges} = changes;
    const identifiers = {session: packet.session, id: observation.id, predecessor: observation.predecessor, submittedToken: packet.basis.token};
    if (changes.outcome === 'unknown') { deferred[index].resolve({...identifiers, outcome: 'unknown'}); await flush(); return; }
    const capture = observation.kind === 'key' ? null : observation.after;
    const ending = observation.kind === 'composition' && ['commit', 'cancel'].includes(observation.data.operation);
    const transaction = observation.kind === 'composition' ? ending ? '0' : observation.transaction : owner.composition;
    const next = receiptChanges.basis ?? frame({value: capture?.value ?? owner.surrounding,
      first: capture?.selectionStart ?? utf16(owner.surrounding, owner.selection[0]),
      last: capture?.selectionEnd ?? utf16(owner.surrounding, owner.selection[1]),
      backward: capture ? capture.selectionDirection === 'backward' : owner.backward,
      context: owner.identity.context, composition: transaction,
      token: String(10000n + ++receiptSerial), revision: String(10000000000000000n + receiptSerial * 17n)}).basis;
    if (!receiptChanges.basis) next.identity = clone(owner.identity);
    const composition = observation.kind === 'composition' ? {transaction: observation.transaction, state: ending ? 'ended' : 'live'} :
      compositions.get(packet.session) ?? (owner.composition !== '0' ? {transaction: owner.composition, state: 'live'} : null);
    const defaultToken = observation.kind === 'key' && observation.data.phase === 'down' && observation.group !== null ?
      {token: String(8000 + index), group: observation.group} : null;
    const receipt = {...identifiers, outcome: 'applied', basis: next, continuity: 'same', defaultToken, composition, ...receiptChanges};
    const nextFrame = frame({value: next.surrounding, first: utf16(next.surrounding, next.selection[0]),
      last: utf16(next.surrounding, next.selection[1]), backward: next.backward, context: next.identity.context,
      revision: next.editorRevision, token: next.token, composition: next.composition,
      policyComposition: policyComposition === undefined ? receipt.composition && receipt.composition.state !== 'ended' ? receipt.composition.transaction : null : policyComposition,
      supported: acceptedFrame.state.capabilities.supported, focused: acceptedFrame.state.focused, active: acceptedFrame.state.active,
      serviceActive: acceptedFrame.state.serviceActive, available: acceptedFrame.state.presentation.available,
      editable: acceptedFrame.state.presentation.editor.editable});
    nextFrame.basis = clone(next); nextFrame.state.presentation.identity = clone(next.identity);
    nextFrame.snapshot.revision = next.identity.presentationRevision;
    const current = context(acceptedFrame.basis) === context(packet.basis) && acceptedFrame.basis.token === packet.basis.token;
    if (current) { register(nextFrame, identifiers); if (publication === 'before') publish(nextFrame, identifiers); }
    owners.set(packet.session, receipt.basis);
    compositions.set(packet.session, receipt.composition?.state === 'ended' ? null : receipt.composition);
    deferred[index].resolve(receipt); await flush();
    if (current && publication === 'after') { publish(nextFrame, identifiers); await flush(); }
    return receipt;
  };
  return {root, document, host, surface, editor, operations, sent, deferred, errors, revoked, resync, traces, captureEvents, publish, answer,
    get initial() { return acceptedFrame; }, element: () => root.children.find(node => node.tagName === 'TEXTAREA') ?? null,
    setResolver: value => { resolver = value; }, restoreResolver: () => { resolver = defaultResolver; },
    async connect() { publish(initial); const pending = surface.connect(); assert.equal(surface.capabilities(), 0n); acknowledge({});
      assert.equal(await pending, true); await flush(); },
    async finish() { await flush(); for (let index = 0; index < sent.length; ++index) await answer(index); }};
}

const down = (node, key = 'a', code = 'KeyA', values = {}) => node.dispatch('keydown', {key, code, ...values});
const up = (node, key = 'a', code = 'KeyA', values = {}) => node.dispatch('keyup', {key, code, ...values});
function passage(node, text) {
  const event = node.dispatch('beforeinput', {inputType: 'insertText', data: text});
  if (!event.defaultPrevented) {
    const first = node.selectionStart, last = node.selectionEnd;
    node.value = node.value.slice(0, first) + text + node.value.slice(last); node.setSelectionRange(first + text.length, first + text.length);
    node.dispatch('input', {inputType: 'insertText', data: text, cancelable: false});
  }
  return event;
}
const legacyEdits = f => f.operations.filter(operation => operation.type === 'surfaceInput' && ['key', 'text', 'composition', 'selection'].includes(operation.input.kind));
function healthy(f) { assert.deepEqual(f.errors, []); assert.deepEqual(f.resync, []); }

test('editor wrapper explicitly negotiates strict v2 and activates only an actual joined owner basis', async () => {
  const f = fixture({initial: frame({value: 'aé😀z', first: 1, last: 4, backward: true})});
  assert.equal(f.element(), null); await f.connect();
  assert.deepEqual(f.operations[0], {type: 'surfaceConnect', version: 2, profile: 'editor_v1', supported: '63'});
  assert.equal(validateSurfaceOperation(f.operations[0], f.initial.snapshot, null, 'editor_v1'), f.operations[0]);
  assert.equal(f.surface.capabilities(), 63n); assert.equal(f.root.children.length, 1);
  const node = f.element(); assert.equal(f.document.activeElement, node); assert.equal(f.root.contains(node), true);
  assert.equal(node.value, 'aé😀z'); assert.deepEqual([node.selectionStart, node.selectionEnd, node.selectionDirection], [1, 4, 'backward']);
  assert.equal(node.style.left, '13px'); assert.equal(node.style.top, '24px');
  assert.equal(f.operations.some(operation => operation.input?.kind === 'focus' && !operation.input.focused), false);
  f.document.flushSelection(); await flush(); assert.equal(f.sent.length, 0); assert.equal(legacyEdits(f).length, 0);
  healthy(f); f.surface.close();
});

test('equal identity and owner fields join regardless of object property insertion order', async () => {
  const initial = frame({value: 'same'}), identity = initial.basis.identity;
  initial.basis.identity = {context: identity.context, epoch: identity.epoch, generation: identity.generation,
    presentationRevision: identity.presentationRevision, owner: {generation: identity.owner.generation, id: identity.owner.id}};
  const f = fixture({initial}); await f.connect();
  assert.equal(f.element().value, 'same'); assert.equal(f.root.children.length, 1); healthy(f); f.surface.close();
});

test('editor profile construction requires every authoritative hook before installing listeners', () => {
  const complete = {resolveBasis() {}, sendObservation() {}, revoke() {}, resync() {}};
  for (const missing of Object.keys(complete)) {
    const editor = {...complete}; delete editor[missing]; const document = new Target(), root = new Target();
    assert.throws(() => createBrowserEditorSurface({root, document, editor, send() {}, resolveOwner() {}}));
    assert.equal(document.listenerCount(), 0); assert.equal(root.listenerCount(), 0);
  }
  assert.throws(() => createBrowserSurface({root: {}, document: {}, profile: 'editor_v1', editor: {}, send() {}, resolveOwner() {}}));
  assert.throws(() => createBrowserEditorSurface({root: {}, document: {}, send() {}, resolveOwner() {}}));
});

test('a supplied mouse classifier adds only the admitted mouse version to the explicit editor offer', async () => {
  const f = fixture({initial: frame({supported: '8255'}), classifyContext: () => 'pointer'}); await f.connect();
  assert.deepEqual(f.operations[0], {type: 'surfaceConnect', version: 2, profile: 'editor_v1', supported: '8255', mouseInputVersion: 1});
  assert.equal(f.surface.capabilities(), 8255n); assert.equal(f.element().value, ''); healthy(f); f.surface.close();
});

test('v1 or mislabeled public states cannot enter the explicit v2 editor profile', () => {
  for (const change of [{version: 1}, {profile: 'mouse_v1'}]) {
    const f = fixture(), next = frame(); Object.assign(next.state, change);
    assert.throws(() => f.publish(next)); assert.equal(f.element(), null); assert.equal(f.operations.length, 0); f.surface.close();
  }
});

test('document capture observes the same trusted textarea key without stealing or duplicating its observation lane', async () => {
  const f = fixture(); await f.connect(); const node = f.element();
  const key = down(node); assert.equal(f.captureEvents[0], key); assert.equal(key.target, node); assert.equal(key.defaultPrevented, false);
  passage(node, 'a'); up(node); down(node, 'b', 'KeyB'); passage(node, 'b'); up(node, 'b', 'KeyB');
  assert.equal(node.value, 'ab'); await flush(); assert.equal(f.sent.length, 1); assert.equal(legacyEdits(f).length, 0);
  for (let index = 0; index < 6; ++index) { await f.answer(index); if (index < 5) assert.equal(node.value, 'ab'); }
  assert.deepEqual(f.sent.map(packet => packet.observation.kind), ['key', 'text', 'key', 'key', 'text', 'key']);
  assert.equal(f.sent[1].basis.editorRevision, '10000000000000017'); assert.equal(f.sent[1].defaultToken, '8000');
  assert.equal(f.sent[4].observation.before.value, 'a'); assert.equal(f.sent[4].observation.after.value, 'ab');
  assert.equal(legacyEdits(f).length, 0); f.document.flushSelection(); await flush(); assert.equal(f.sent.length, 6);
  healthy(f); f.surface.close();
});

test('owner receipt preceding the UI state delivery does not reset a provisional typing burst', async () => {
  const f = fixture(); await f.connect(); const node = f.element(); down(node); passage(node, 'a'); up(node);
  down(node, 'b', 'KeyB'); passage(node, 'b'); up(node, 'b', 'KeyB'); await flush();
  for (let index = 0; index < 6; ++index) { await f.answer(index, {publication: 'after'}); assert.equal(f.element(), node); assert.equal(node.value, 'ab'); }
  assert.equal(f.sent.length, 6); assert.equal(legacyEdits(f).length, 0); healthy(f); f.surface.close();
});

test('same-token presentation-only refresh keeps the native passage and uses the actual later owner identity', async () => {
  const f = fixture(); await f.connect(); const node = f.element(); down(node); passage(node, 'a'); up(node); await flush();
  const refresh = clone(f.initial), revision = '9007199254740994';
  refresh.snapshot.revision = revision; refresh.state.presentation.identity.presentationRevision = revision;
  refresh.basis.identity.presentationRevision = revision; f.publish(refresh);
  assert.equal(f.element(), node); assert.equal(node.value, 'a'); assert.equal(f.sent.length, 1);
  const returned = clone(refresh.basis); returned.token = '301'; returned.editorRevision = '9007199254741011';
  await f.answer(0, {basis: returned}); assert.equal(f.sent[1].basis.identity.presentationRevision, revision);
  await f.answer(1); await f.answer(2); assert.equal(f.element(), node); assert.equal(node.value, 'a');
  assert.equal(legacyEdits(f).length, 0); healthy(f); f.surface.close();
});

test('untrusted textarea callbacks cannot fall through document capture into public raw-key delivery', async () => {
  const f = fixture(); await f.connect(); const node = f.element();
  down(node, 'a', 'KeyA', {isTrusted: false}); up(node, 'a', 'KeyA', {isTrusted: false});
  node.dispatch('beforeinput', {inputType: 'insertText', data: 'a', isTrusted: false});
  node.dispatch('input', {inputType: 'insertText', data: 'a', isTrusted: false});
  await flush(); assert.equal(f.sent.length, 0); assert.equal(legacyEdits(f).length, 0); healthy(f); f.surface.close();
});

test('native composition callbacks traverse document capture but export only the private checked composition chain', async () => {
  const f = fixture(); await f.connect(); const node = f.element(); down(node, 'Process', 'KeyA');
  node.dispatch('compositionstart', {data: '', cancelable: false}); up(node, 'Process', 'KeyA', {isComposing: true});
  node.dispatch('beforeinput', {inputType: 'insertCompositionText', data: '漢', isComposing: true, cancelable: false});
  node.dispatch('compositionupdate', {data: '漢', cancelable: false}); node.value = '漢'; node.setSelectionRange(1, 1);
  node.dispatch('input', {inputType: 'insertCompositionText', data: '漢', isComposing: true, cancelable: false});
  node.dispatch('compositionend', {data: '漢', cancelable: false}); await f.finish();
  assert.deepEqual(f.sent.map(packet => packet.observation.kind), ['key', 'composition', 'key', 'composition', 'composition']);
  assert.equal(f.sent[1].defaultToken, '8000'); assert.equal(f.sent[3].observation.authority, 'composition');
  assert.equal(node.value, '漢'); assert.equal(legacyEdits(f).length, 0); healthy(f); f.surface.close();
});

test('a checked logical pending transaction keeps native attestation zero until the actual live preedit readback', async () => {
  const f = fixture(); await f.connect(); const node = f.element(); down(node, 'Process', 'KeyA');
  node.dispatch('compositionstart', {data: '', cancelable: false}); up(node, 'Process', 'KeyA', {isComposing: true});
  node.dispatch('beforeinput', {inputType: 'insertCompositionText', data: '漢', isComposing: true, cancelable: false});
  node.dispatch('compositionupdate', {data: '漢', cancelable: false}); node.value = '漢'; node.setSelectionRange(1, 1);
  node.dispatch('input', {inputType: 'insertCompositionText', data: '漢', isComposing: true, cancelable: false});
  node.dispatch('compositionend', {data: '漢', cancelable: false}); await flush(); await f.answer(0);
  const transaction = f.sent[1].observation.transaction;
  await f.answer(1, {basis: frame({token: '501', revision: '9007199254741021'}).basis,
    composition: {transaction, state: 'pending'}});
  assert.equal(f.initial.state.composition, transaction); assert.equal(f.initial.state.presentation.editor.compositionTransaction, '0');
  assert.equal(f.element(), node); assert.equal(node.value, '漢'); assert.equal(f.sent[2].basis.composition, '0');
  await f.answer(2); assert.equal(f.initial.state.composition, transaction); assert.equal(f.initial.basis.composition, '0');
  assert.equal(f.element(), node); assert.equal(node.value, '漢'); await f.answer(3);
  assert.equal(f.initial.state.composition, transaction); assert.equal(f.initial.basis.composition, transaction);
  await f.answer(4); assert.equal(f.initial.state.composition, null); assert.equal(f.initial.basis.composition, '0');
  assert.equal(f.element(), node); assert.equal(node.value, '漢'); assert.equal(legacyEdits(f).length, 0); healthy(f); f.surface.close();
});

for (const native of ['0', '71']) test(`an initial untagged Policy transaction with native attestation ${native} cannot fabricate a resumed textarea`, async () => {
  const f = fixture({initial: frame({value: 'preedit', composition: native, policyComposition: '71'})}); await f.connect();
  assert.equal(f.element(), null); assert.equal(f.sent.length, 0); assert.ok(f.resync.length); assert.deepEqual(f.errors, []); f.surface.close();
});

for (const native of ['0', '71']) test(`an external untagged Policy transaction with native attestation ${native} retires the old local passage`, async () => {
  const f = fixture(); await f.connect(); const old = f.element(); down(old); passage(old, 'a'); await flush();
  f.publish(frame({value: 'external preedit', revision: '9007199254741022', token: '503', composition: native, policyComposition: '71'}));
  assert.equal(f.element(), null); assert.equal(old.listenerCount(), 0); assert.ok(f.resync.length);
  await f.answer(0, {publication: 'none'}); assert.equal(f.element(), null); assert.equal(f.sent.length, 1); assert.deepEqual(f.errors, []); f.surface.close();
});

test('an untagged same-token logical pending transaction is not a presentation-only refresh', async () => {
  const f = fixture(); await f.connect(); const old = f.element(); down(old); passage(old, 'a'); await flush();
  f.publish(frame({policyComposition: '71'})); assert.equal(f.element(), null); assert.equal(old.listenerCount(), 0); assert.ok(f.resync.length);
  await f.answer(0, {publication: 'none'}); assert.equal(f.element(), null); assert.equal(f.sent.length, 1); assert.deepEqual(f.errors, []); f.surface.close();
});

test('a head-tagged UI logical transaction must agree with the checked pending receipt before another observation drains', async () => {
  const f = fixture(); await f.connect(); const node = f.element(); node.dispatch('compositionstart', {data: '', cancelable: false});
  node.dispatch('beforeinput', {inputType: 'insertCompositionText', data: '漢', isComposing: true, cancelable: false});
  node.dispatch('compositionupdate', {data: '漢', cancelable: false}); node.value = '漢'; node.setSelectionRange(1, 1);
  node.dispatch('input', {inputType: 'insertCompositionText', data: '漢', isComposing: true, cancelable: false}); await flush();
  const transaction = f.sent[0].observation.transaction, publicCount = f.operations.length;
  await f.answer(0, {basis: frame({token: '504', revision: '9007199254741023'}).basis,
    composition: {transaction, state: 'pending'}, policyComposition: '999'});
  assert.equal(f.element(), null); assert.equal(node.listenerCount(), 0); assert.equal(f.sent.length, 1);
  assert.equal(f.errors.length, 1); assert.deepEqual(f.resync, []); assert.deepEqual(f.revoked, []);
  assert.equal(f.operations.length, publicCount); f.surface.close();
});

test('the resolver receives cloned arguments and cannot mutate the main accepted surface or snapshot', async () => {
  const initial = frame({value: 'owner'});
  const f = fixture({initial, resolveBasis(snapshot, surface) {
    snapshot.closed = true; snapshot.widgets.length = 0; surface.focused = false; surface.presentation.editor = null;
    return {basis: initial.basis, settlement: null};
  }}); await f.connect();
  assert.equal(f.element().value, 'owner'); assert.equal(f.surface.owns(initial.state.presentation.identity.owner), true);
  assert.equal(f.surface.capabilities(), 63n); healthy(f); f.surface.close();
});

test('settlement accessors are rejected without invoking a getter that could publish another context', async () => {
  const f = fixture(); await f.connect(); const old = f.element(); down(old); passage(old, 'a'); await flush();
  const head = f.sent[0], next = frame({value: 'outer', context: '14', token: '601'}), inner = frame({value: 'getter', context: '15', token: '602'});
  let reads = 0, rejected = false;
  const settlement = {id: head.observation.id, predecessor: head.observation.predecessor, submittedToken: head.basis.token};
  Object.defineProperty(settlement, 'session', {enumerable: true, get() {
    ++reads; if (reads === 1) { f.setResolver(() => ({basis: inner.basis, settlement: null})); f.publish(inner); } return head.session;
  }});
  f.setResolver(() => ({basis: next.basis, settlement}));
  try { f.publish(next); } catch { rejected = true; }
  assert.equal(reads, 0); assert.equal(f.element(), null); assert.equal(old.listenerCount(), 0);
  assert.ok(rejected || f.resync.length || f.errors.length); await f.answer(0, {publication: 'none'});
  assert.equal(f.sent.length, 1); f.surface.close();
});

for (const loss of ['window blur', 'owner rejection', 'resync']) test(`${loss} cannot be undone by an untagged repaint of the same native token`, async () => {
  const f = fixture(); await f.connect(); const old = f.element(), original = clone(f.initial);
  if (loss === 'window blur') f.host.dispatch('blur', {cancelable: false});
  else if (loss === 'owner rejection') {
    down(old); passage(old, 'a'); await flush();
    await f.answer(0, {outcome: 'rejected', basis: original.basis, defaultToken: null, publication: 'none'});
  } else old.dispatch('beforeinput', {inputType: 'deleteContentBackward', data: null});
  assert.equal(f.element(), null); const count = f.sent.length;
  f.publish(original); assert.equal(f.element(), null); down(old, 'z', 'KeyZ'); passage(old, 'z'); await flush(); assert.equal(f.sent.length, count);
  f.publish(frame({token: '603'})); const next = f.element(); assert.ok(next); assert.notEqual(next, old);
  down(next); passage(next, 'a'); up(next); await flush(); assert.equal(f.sent.length, count + 1);
  assert.equal(legacyEdits(f).length, 0); assert.deepEqual(f.errors, []); f.surface.close();
});

test('a null actual basis leaves the negotiated editor unavailable without manufacturing a proxy context', async () => {
  const f = fixture({resolveBasis: () => null}); await f.connect();
  assert.equal(f.element(), null); assert.equal(f.sent.length, 0); assert.equal(f.document.activeElement, f.root);
  assert.deepEqual(f.errors, []); f.surface.close();
});

test('an unavailable actual basis never enables the public raw-key fallback while an editor is published', async () => {
  const f = fixture({resolveBasis: () => null}); await f.connect();
  assert.equal(f.element(), null); down(f.root); up(f.root); await flush();
  assert.equal(f.sent.length, 0); assert.equal(legacyEdits(f).length, 0); assert.deepEqual(f.errors, []); f.surface.close();
});

test('a checked noneditable body state retains the trusted public raw-key route', async () => {
  const initial = frame(); initial.state.presentation.editor = null;
  const f = fixture({initial, resolveBasis() { return {basis: null, settlement: null, retirement: retirementProof(initial.basis)}; }}); await f.connect();
  assert.equal(f.element(), null); down(f.root); up(f.root); await flush();
  assert.equal(f.sent.length, 0); assert.deepEqual(legacyEdits(f).map(operation => operation.input.phase), ['down', 'up']);
  for (const operation of legacyEdits(f)) assert.equal(validateSurfaceOperation(operation, initial.snapshot, initial.state, 'editor_v1'), operation);
  assert.deepEqual(f.errors, []); f.surface.close();
});

for (const [field, mutate] of [
  ['owner id', basis => { basis.identity.owner.id = 'other'; }],
  ['owner generation', basis => { basis.identity.owner.generation = '9007199254740994'; }],
  ['presentation revision', basis => { basis.identity.presentationRevision = '9007199254740994'; }],
  ['generation', basis => { basis.identity.generation = '8'; }],
  ['epoch', basis => { basis.identity.epoch = '12'; }],
  ['context', basis => { basis.identity.context = '14'; }],
  ['editor revision', basis => { basis.editorRevision = '9007199254740994'; }],
  ['surrounding', basis => { basis.surrounding = 'b😀éz'; }],
  ['selection', basis => { basis.selection = [0, 0]; }],
  ['selection direction', basis => { basis.backward = false; }],
  ['composition attestation', basis => { basis.composition = '71'; }]
]) test(`an actual basis with mismatched ${field} cannot enter the accepted public editor context`, async () => {
  const initial = frame({value: 'a😀éz', first: 1, last: 3, backward: true}), bad = clone(initial.basis); mutate(bad);
  const f = fixture({initial, resolveBasis: () => ({basis: bad, settlement: null})}); let rejected = false;
  try { await f.connect(); } catch { rejected = true; }
  await flush(); assert.equal(f.element(), null); assert.equal(f.sent.length, 0); assert.equal(f.document.activeElement, f.root);
  assert.ok(rejected || f.errors.length || f.resync.length, 'A mismatched basis must produce an explicit rejection');
  assert.equal(legacyEdits(f).length, 0); f.surface.close();
});

for (const changed of [{focused: false}, {active: false}, {serviceActive: true}, {available: false}, {editable: false}, {supported: '41'}])
  test(`public editor loss ${JSON.stringify(changed)} retires pending input and rejects late work`, async () => {
    const f = fixture(); await f.connect(); const old = f.element(); down(old); passage(old, 'a'); await flush();
    f.publish(frame(changed)); assert.equal(f.element(), null); assert.equal(old.listenerCount(), 0);
    down(old, 'z', 'KeyZ'); passage(old, 'z'); await f.answer(0);
    assert.equal(f.element(), null); assert.equal(f.sent.length, 1); assert.equal(legacyEdits(f).length, 0); assert.deepEqual(f.errors, []);
    f.surface.close();
  });

for (const loss of ['window blur', 'hidden document']) test(`${loss} immediately retires preedit and its queued tail before owner focus readback`, async () => {
  const f = fixture(); await f.connect(); const old = f.element(); down(old, 'Process', 'KeyA');
  old.dispatch('compositionstart', {data: '', cancelable: false});
  old.dispatch('compositionupdate', {data: 'a', cancelable: false});
  old.dispatch('beforeinput', {inputType: 'insertCompositionText', data: 'a', isComposing: true, cancelable: false});
  old.value = 'a'; old.setSelectionRange(1, 1);
  old.dispatch('input', {inputType: 'insertCompositionText', data: 'a', isComposing: true, cancelable: false});
  await flush(); assert.equal(f.sent.length, 1);
  if (loss === 'window blur') f.host.dispatch('blur', {cancelable: false});
  else { f.document.visibilityState = 'hidden'; f.document.dispatch('visibilitychange', {cancelable: false}); }
  assert.equal(f.element(), null); assert.equal(old.listenerCount(), 0); assert.equal(f.revoked.length, 1);
  assert.notEqual(f.revoked[0].composition, null); assert.equal(f.revoked[0].keys.length, 1);
  // The owner reply belongs to the earlier raw-key operation, before its
  // queued focus/cancel command. It does not republish a fresh focus grant.
  await f.answer(0, {publication: 'none'}); down(old, 'z', 'KeyZ'); passage(old, 'z'); await flush();
  assert.equal(f.element(), null); assert.equal(f.sent.length, 1); assert.equal(legacyEdits(f).length, 0);
  assert.deepEqual(f.errors, []); f.surface.close();
});

for (const token of ['202', '9007199254741001']) test(`context replacement with token ${token} keeps old-flight results out of its successor`, async () => {
  const f = fixture(); await f.connect(); const old = f.element(); down(old); passage(old, 'a'); await flush();
  f.publish(frame({value: 'B', context: '14', token})); const next = f.element();
  assert.notEqual(next, old); assert.equal(old.listenerCount(), 0); assert.equal(next.value, 'B'); assert.equal(f.root.children.length, 1);
  down(next, 'x', 'KeyX'); passage(next, 'x'); up(next, 'x', 'KeyX'); await flush(); assert.equal(f.sent.length, 1);
  await f.answer(0); assert.equal(f.sent.length, 2); assert.equal(f.sent[1].basis.identity.context, '14');
  assert.equal(f.sent[1].basis.token, token); assert.equal(next.value, 'Bx');
  await f.answer(1); await f.answer(2); await f.answer(3); assert.equal(f.element(), next); assert.equal(next.value, 'Bx');
  assert.equal(legacyEdits(f).length, 0); healthy(f); f.surface.close();
});

test('untagged native projection changes replace the provisional tail rather than exporting its queued text', async () => {
  const f = fixture(); await f.connect(); const old = f.element(); down(old); passage(old, 'a'); up(old); await flush();
  f.publish(frame({value: 'native', revision: '9007199254741021', token: '302'})); const next = f.element();
  assert.notEqual(next, old); assert.equal(old.listenerCount(), 0); assert.equal(next.value, 'native');
  await f.answer(0); assert.equal(f.element(), next); assert.equal(next.value, 'native'); assert.equal(f.sent.length, 1);
  assert.equal(legacyEdits(f).length, 0); healthy(f); f.surface.close();
});

test('an unrelated settlement tag cannot preserve an old native passage in a newly accepted context', async () => {
  const f = fixture(); await f.connect(); const old = f.element(); down(old); passage(old, 'a'); await flush();
  const head = f.sent[0], unrelated = {session: head.session, id: String(BigInt(head.observation.id) + 100n),
    predecessor: head.observation.predecessor, submittedToken: head.basis.token};
  f.publish(frame({value: 'other context', context: '14', token: '303'}), unrelated);
  assert.equal(f.element(), null); assert.equal(old.listenerCount(), 0); assert.equal(f.resync.length, 1);
  down(old, 'z', 'KeyZ'); passage(old, 'z'); await f.answer(0);
  assert.equal(f.sent.length, 1); assert.equal(f.element(), null); assert.equal(legacyEdits(f).length, 0); assert.deepEqual(f.errors, []);
  f.surface.close();
});

test('a stale private projection cannot activate a newly published public editor revision', async () => {
  const f = fixture(); await f.connect(); const previous = clone(f.initial.basis);
  f.setResolver(() => ({basis: previous, settlement: null})); let rejected = false;
  try { f.publish(frame({value: 'new', revision: '9007199254740994', token: '203'})); } catch { rejected = true; }
  assert.equal(f.element(), null); assert.equal(f.sent.length, 0);
  assert.ok(rejected || f.errors.length || f.resync.length); f.surface.close();
});

test('a resolver may close the surface without a stale outer accept creating or focusing a new conduit', async () => {
  const f = fixture(); await f.connect(); const old = f.element();
  const next = frame({value: 'outer', context: '14', token: '204'});
  f.setResolver(() => { f.surface.close(); return {basis: next.basis, settlement: null}; }); f.publish(next);
  assert.equal(f.surface.capabilities(), 0n); assert.equal(f.element(), null); assert.equal(f.root.children.length, 0);
  assert.equal(old.listenerCount(), 0); assert.equal(f.sent.length, 0); assert.deepEqual(f.errors, []);
});

test('recursive resolver publication owns the inner context and blocks the stale outer projection', async () => {
  const f = fixture(); await f.connect(); let entered = false;
  const outer = frame({value: 'outer', context: '14', token: '205'}), inner = frame({value: 'inner', context: '15', token: '206'});
  f.setResolver(() => { if (!entered) { entered = true; f.publish(inner); return {basis: outer.basis, settlement: null}; }
    return {basis: inner.basis, settlement: null}; });
  f.publish(outer); assert.equal(f.element().value, 'inner'); assert.equal(f.root.children.length, 1);
  down(f.element()); passage(f.element(), 'a'); await flush(); assert.equal(f.sent[0].basis.identity.context, '15');
  assert.equal(f.sent[0].basis.token, '206'); assert.equal(legacyEdits(f).length, 0); healthy(f); f.surface.close();
});

test('recursive revoke publication retains its winning owner without an outer resync revoking it', async () => {
  let f, entered = false;
  const inner = frame({value: 'winner', context: '15', token: '208'});
  f = fixture({onRevoke() { if (!entered) { entered = true; f.publish(inner); } }}); await f.connect();
  f.publish(frame({value: 'outer', context: '14', token: '207'}));
  assert.equal(f.element().value, 'winner'); assert.equal(f.root.children.length, 1);
  down(f.element()); await flush(); assert.equal(f.sent[0].basis.identity.context, '15'); assert.equal(f.sent[0].basis.token, '208');
  assert.equal(legacyEdits(f).length, 0); healthy(f); f.surface.close();
});

for (const outcome of ['unknown', 'transport rejection']) test(`${outcome} retires only local DOM state without cleanup commands or revival`, async () => {
  const f = fixture(); await f.connect(); const old = f.element(); down(old); passage(old, 'a'); up(old); await flush();
  const publicCount = f.operations.length;
  if (outcome === 'unknown') await f.answer(0, {outcome: 'unknown'});
  else { f.deferred[0].reject(Error('Owner reply transport failed')); await flush(); }
  assert.equal(f.element(), null); assert.equal(old.listenerCount(), 0); assert.equal(f.revoked.length, 0);
  assert.deepEqual(f.resync, []); assert.equal(f.errors.length, 1); assert.equal(f.operations.length, publicCount);
  f.publish(frame({value: 'later', context: '14', token: '209'})); down(old, 'z', 'KeyZ'); passage(old, 'z'); await flush();
  assert.equal(f.element(), null); assert.equal(f.sent.length, 1); assert.equal(f.revoked.length, 0);
  assert.equal(f.operations.length, publicCount); f.surface.close();
});

test('terminal onFailure reentry cannot accept a body fallback or export raw key, focus or pointer cleanup', async () => {
  let f;
  f = fixture({onFailure() {
    const body = frame(); body.state.presentation.editor = null; f.publish(body); f.root.focus();
    down(f.root, 'z', 'KeyZ'); up(f.root, 'z', 'KeyZ'); f.host.dispatch('blur', {cancelable: false}); f.surface.cancelPointers();
  }}); await f.connect(); const old = f.element(); down(old); passage(old, 'a'); await flush(); const count = f.operations.length;
  await f.answer(0, {outcome: 'unknown'});
  assert.equal(f.operations.length, count); assert.equal(f.errors.length, 1); assert.equal(f.element(), null);
  assert.deepEqual(f.revoked, []); assert.deepEqual(f.resync, []); assert.equal(f.sent.length, 1); f.surface.close();
});

test('receipt basis accessors never run before terminal validation or gain callback publication authority', async () => {
  const f = fixture(); await f.connect(); const old = f.element(); down(old); passage(old, 'a'); await flush();
  const packet = f.sent[0], receipt = {session: packet.session, id: packet.observation.id, predecessor: packet.observation.predecessor,
    submittedToken: packet.basis.token, outcome: 'applied', continuity: 'same', defaultToken: null, composition: null};
  let reads = 0; const count = f.operations.length;
  Object.defineProperty(receipt, 'basis', {enumerable: true, get() {
    ++reads; const body = frame(); body.state.presentation.editor = null; f.publish(body); f.root.focus(); down(f.root, 'z', 'KeyZ'); return body.basis;
  }});
  f.deferred[0].resolve(receipt); await flush();
  assert.equal(reads, 0); assert.equal(f.errors.length, 1); assert.equal(f.element(), null); assert.equal(old.listenerCount(), 0);
  assert.deepEqual(f.revoked, []); assert.deepEqual(f.resync, []); assert.equal(f.operations.length, count); assert.equal(f.sent.length, 1); f.surface.close();
});


function retirementProof(basis, availability = 'noneditable', authorityRetired = false) {
  return {availability, identity: clone(basis.identity), observationRevision: '18446744073709551615',
    readbackAttested: true, ...(authorityRetired ? {authorityRetired: true} : {})};
}
function retirementReceipt(packet, retirement, outcome = 'applied') {
  return {session: packet.session, id: packet.observation.id, predecessor: packet.observation.predecessor,
    submittedToken: packet.basis.token, outcome, continuity: 'replaced', basis: null,
    defaultToken: null, composition: null, retirement: clone(retirement)};
}
function nullPublication(f, packet, retirement, {redacted = false, settlement = true} = {}) {
  const next = frame(); next.basis = null; next.state.presentation.editor = null;
  next.state.presentation.identity = clone(packet.basis.identity); next.snapshot.revision = packet.basis.identity.presentationRevision;
  if (redacted) { next.state.presentation = null; next.snapshot.widgets = []; }
  const tag = settlement ? {session: packet.session, id: packet.observation.id,
    predecessor: packet.observation.predecessor, submittedToken: packet.basis.token} : null;
  f.setResolver(() => ({basis: null, settlement: clone(tag), retirement: clone(retirement)}));
  f.publish(next); return next;
}
for (const outcome of ['applied', 'cancelled', 'rejected']) for (const publication of ['before', 'after'])
  for (const redacted of [false, true]) test(`checked ${outcome} retirement joins ${publication} receipt with redacted=${redacted}`, async () => {
    const f = fixture(); await f.connect(); const old = f.element(); down(old, 'Tab', 'Tab'); await flush();
    const packet = f.sent[0], proof = retirementProof(packet.basis);
    if (publication === 'before') nullPublication(f, packet, proof, {redacted});
    f.deferred[0].resolve(retirementReceipt(packet, proof, outcome)); await flush();
    if (publication === 'after') { nullPublication(f, packet, proof, {redacted}); await flush(); }
    assert.equal(f.element(), null); assert.equal(f.sent.length, 1); assert.deepEqual(f.errors, []);
    assert.ok(f.resync.some(value => value.basis === null));
    const count = legacyEdits(f).length; f.root.focus(); down(f.root, 'b', 'KeyB'); up(f.root, 'b', 'KeyB');
    assert.equal(legacyEdits(f).length, count + (redacted ? 0 : 2));
    down(old, 'z', 'KeyZ'); assert.equal(f.sent.length, 1); f.surface.close();
  });
for (const availability of ['unavailable', 'available']) test(`checked ${availability} null retirement grants no body keys`, async () => {
  const f = fixture(); await f.connect(); down(f.element(), 'Tab', 'Tab'); await flush();
  const packet = f.sent[0], proof = retirementProof(packet.basis, availability, availability === 'available');
  nullPublication(f, packet, proof); f.deferred[0].resolve(retirementReceipt(packet, proof)); await flush();
  f.root.focus(); down(f.root); up(f.root); assert.equal(legacyEdits(f).length, 0);
  assert.equal(f.element(), null); assert.deepEqual(f.errors, []); f.surface.close();
});
test('a public null editor without a checked noneditable sample cannot route raw keys', async () => {
  const initial = frame(); initial.state.presentation.editor = null;
  const f = fixture({initial, resolveBasis: () => null}); await f.connect();
  down(f.root); up(f.root); assert.equal(legacyEdits(f).length, 0); assert.deepEqual(f.errors, []); f.surface.close();
});
test('an applied effect retired by service before its reply settles only the original head', async () => {
  const f = fixture(); await f.connect(); const old = f.element(); passage(old, 'x'); await flush();
  const packet = f.sent[0], unavailable = frame({serviceActive: true}); f.publish(unavailable);
  assert.equal(f.element(), null); const proof = retirementProof(packet.basis, 'available', true);
  nullPublication(f, packet, proof, {redacted: true}); f.deferred[0].resolve(retirementReceipt(packet, proof, 'applied')); await flush();
  assert.equal(f.element(), null); assert.equal(f.sent.length, 1); assert.deepEqual(f.errors, []);
  const count = f.operations.length; f.root.focus(); down(f.root); assert.equal(f.operations.length, count);
  f.surface.close();
});
test('a null retirement publication cannot replace the checked receipt observation revision', async () => {
  const f = fixture(); await f.connect(); down(f.element(), 'Tab', 'Tab'); await flush();
  const packet = f.sent[0], proof = retirementProof(packet.basis), bad = {...proof, observationRevision: '7'};
  nullPublication(f, packet, bad, {redacted: true}); f.deferred[0].resolve(retirementReceipt(packet, proof)); await flush();
  assert.equal(f.errors.length, 1); assert.equal(f.surface.capabilities(), 0n); assert.equal(f.element(), null);
});
test('checked retirement cannot reactivate the exact retired native token', async () => {
  const f = fixture(); await f.connect(); const original = clone(f.initial); down(f.element(), 'Tab', 'Tab'); await flush();
  const packet = f.sent[0], proof = retirementProof(packet.basis);
  nullPublication(f, packet, proof); f.deferred[0].resolve(retirementReceipt(packet, proof)); await flush();
  f.setResolver(() => ({basis: original.basis, settlement: null})); f.publish(original);
  assert.equal(f.element(), null); assert.equal(f.sent.length, 1); assert.deepEqual(f.errors, []); f.surface.close();
});

test('a checked retirement fences an advanced token even before its projection publication', async () => {
  const f = fixture(); await f.connect(); down(f.element(), 'ArrowRight', 'ArrowRight'); await flush();
  const receipt = await f.answer(0, {publication: 'none'});
  const advanced = frame({token: receipt.basis.token, revision: receipt.basis.editorRevision});
  advanced.basis = clone(receipt.basis); advanced.state.presentation.identity = clone(receipt.basis.identity);
  advanced.snapshot.revision = receipt.basis.identity.presentationRevision;
  down(f.element(), 'Tab', 'Tab'); await flush();
  const packet = f.sent[1]; assert.equal(packet.basis.token, advanced.basis.token);
  const proof = retirementProof(packet.basis); nullPublication(f, packet, proof);
  f.deferred[1].resolve(retirementReceipt(packet, proof)); await flush();
  f.setResolver(() => ({basis: advanced.basis, settlement: null})); f.publish(advanced);
  assert.equal(f.element(), null); assert.equal(f.sent.length, 2); assert.deepEqual(f.errors, []); f.surface.close();
});
test('an independent null sample cannot route raw keys while the original head is unsettled', async () => {
  const f = fixture(); await f.connect(); down(f.element(), 'Tab', 'Tab'); await flush();
  const packet = f.sent[0], proof = retirementProof(packet.basis); nullPublication(f, packet, proof, {settlement: false});
  f.root.focus(); down(f.root); up(f.root); assert.equal(legacyEdits(f).length, 0);
  f.deferred[0].resolve(retirementReceipt(packet, proof)); await flush(); assert.deepEqual(f.errors, []); f.surface.close();
});
for (const malformed of ['available-without-authority', 'false-authority', 'extra-field', 'wrong-owner'])
  test(`a malformed head-tagged null publication is terminal: ${malformed}`, async () => {
    const f = fixture(); await f.connect(); down(f.element(), 'Tab', 'Tab'); await flush();
    const packet = f.sent[0], proof = retirementProof(packet.basis);
    if (malformed === 'available-without-authority') proof.availability = 'available';
    if (malformed === 'false-authority') proof.authorityRetired = false;
    if (malformed === 'extra-field') proof.extra = true;
    if (malformed === 'wrong-owner') proof.identity.owner.id = 'foreign';
    nullPublication(f, packet, proof, {redacted: true}); assert.equal(f.errors.length, 1);
    assert.equal(f.surface.capabilities(), 0n); assert.equal(f.element(), null);
    f.deferred[0].resolve(retirementReceipt(packet, retirementProof(packet.basis))); await flush();
    assert.equal(f.sent.length, 1); assert.equal(f.errors.length, 1);
  });

// v6 model continuation: JS records actual trusted body ingress. Only the App
// can join a provider-consumed down and its full engine target/native core.
function bodyFixture(supported = '63', options = {}) {
  const initial = frame({supported}); initial.state.presentation.editor = null;
  return fixture({...options, initial, resolveBasis: () => ({basis: null, settlement: null, retirement: retirementProof(initial.basis)}),
    ...(supported === '8255' ? {classifyContext: () => 'pointer'} : {})});
}
for (const supported of ['63', '8255']) for (const publishedEditor of [false, true])
  test(`a real held body keyup crosses only the pending admission fence: ${supported}/${publishedEditor}`, async () => {
    const f = bodyFixture(supported); await f.connect(); down(f.root, 'F5', 'F5');
    const pending = clone(f.initial);
    if (publishedEditor) pending.state.presentation.editor = frame({supported}).state.presentation.editor;
    f.setResolver(() => null); f.publish(pending);
    down(f.root, 'q', 'KeyQ', {ctrlKey: true}); down(f.root, 'F5', 'F5', {repeat: true});
    assert.deepEqual(legacyEdits(f).map(value => value.input.phase), ['down']);
    up(f.root, 'F5', 'F5', {repeat: true}); up(f.root, 'F5', 'F5'); down(f.root, 'F5', 'F5');
    const keys = legacyEdits(f); assert.deepEqual(keys.map(value => value.input.phase), ['down', 'up']);
    assert.equal(keys[1].input.repeat, false); assert.equal(keys[1].input.key, 'F5');
    assert.deepEqual(keys[1].identity, keys[0].identity); assert.equal(f.sent.length, 0);
    assert.deepEqual(f.errors, []); f.surface.close();
  });
test('a held body release permits only presentation revision aliasing', async () => {
  const f = bodyFixture(); await f.connect(); down(f.root, 'F5', 'F5');
  const pending = clone(f.initial), next = '9007199254740994';
  pending.snapshot.revision = next; pending.state.presentation.identity.presentationRevision = next;
  f.setResolver(() => null); f.publish(pending); up(f.root, 'F5', 'F5');
  const keys = legacyEdits(f); assert.equal(keys.length, 2);
  assert.equal(keys[0].identity.presentationRevision, wide); assert.equal(keys[1].identity.presentationRevision, next);
  assert.equal(validateSurfaceOperation(keys[1], pending.snapshot, pending.state, 'editor_v1'), keys[1]);
  assert.deepEqual(f.errors, []); f.surface.close();
});
for (const changed of ['owner', 'owner-generation', 'generation', 'epoch', 'context'])
  test(`a held body release cannot move to a successor ${changed}`, async () => {
    const f = bodyFixture(); await f.connect(); down(f.root, 'F5', 'F5');
    const pending = clone(f.initial), identity = pending.state.presentation.identity;
    if (changed === 'owner') identity.owner.id = 'other';
    else if (changed === 'owner-generation') identity.owner.generation = '9007199254740994';
    else identity[changed] = String(BigInt(identity[changed]) + 1n);
    pending.snapshot.widgets[0].key = clone(identity.owner);
    f.setResolver(() => null); f.publish(pending); up(f.root, 'F5', 'F5');
    assert.deepEqual(legacyEdits(f).map(value => value.input.phase), ['down']); assert.deepEqual(f.errors, []); f.surface.close();
  });
for (const bad of ['untrusted', 'key', 'code', 'location', 'foreign-target', 'invalid-key'])
  test(`a held body release requires actual matching provenance: ${bad}`, async () => {
    const f = bodyFixture(); await f.connect(); down(f.root, 'F5', 'F5');
    f.setResolver(() => null); f.publish(clone(f.initial));
    if (bad === 'foreign-target') f.document.dispatch('keyup', {key: 'F5', code: 'F5'});
    else up(f.root, bad === 'key' ? 'F6' : bad === 'invalid-key' ? '\0' : 'F5', bad === 'code' ? 'F6' : 'F5',
      {...(bad === 'untrusted' ? {isTrusted: false} : {}), ...(bad === 'location' ? {location: 1} : {})});
    assert.deepEqual(legacyEdits(f).map(value => value.input.phase), bad === 'key' ? ['down', 'up'] : ['down']);
    if (bad === 'key') assert.equal(legacyEdits(f)[1].input.key, 'F6');
    up(f.root, 'F5', 'F5'); assert.deepEqual(legacyEdits(f).map(value => value.input.phase), ['down', 'up']);
    assert.deepEqual(f.errors, []); f.surface.close();
  });
for (const loss of ['blur', 'hidden', 'service', 'unavailable', 'closed'])
  test(`body release authority is retired on actual ${loss}`, async () => {
    const f = bodyFixture(); await f.connect(); down(f.root, 'F5', 'F5');
    f.setResolver(() => null);
    if (loss === 'blur') f.host.dispatch('blur', {cancelable: false});
    else if (loss === 'hidden') { f.document.visibilityState = 'hidden'; f.document.dispatch('visibilitychange', {cancelable: false}); }
    else { const pending = clone(f.initial); if (loss === 'service') pending.state.serviceActive = true;
      if (loss === 'unavailable') pending.state.presentation.available = false;
      if (loss === 'closed') pending.snapshot.closed = true; f.publish(pending); }
    up(f.root, 'F5', 'F5'); assert.deepEqual(legacyEdits(f).map(value => value.input.phase), ['down']);
    assert.deepEqual(f.errors, []); f.surface.close();
  });

for (const boundary of ['ingress-focus', 'before-export-focus'])
  test(`body ingress cannot retarget after callback retirement at ${boundary}`, async () => {
    let f, armed = false, reads = 0;
    f = bodyFixture('63', {onResolveOwner() {
      if (armed && ++reads === (boundary === 'ingress-focus' ? 1 : 3)) {
        armed = false; const successor = frame({context: '14'}); successor.state.presentation.editor = null;
        f.setResolver(() => ({basis: null, settlement: null, retirement: retirementProof(successor.basis)})); f.publish(successor);
      }
    }}); await f.connect(); armed = true; down(f.root, 'F5', 'F5'); up(f.root, 'F5', 'F5');
    assert.equal(legacyEdits(f).length, 0); assert.deepEqual(f.errors, []); f.surface.close();
  });
test('a recursive model keyup before export cannot precede or strand its body down', async () => {
  let f, armed = false, reads = 0;
  f = bodyFixture('63', {onResolveOwner() { if (armed && ++reads === 3) { armed = false; up(f.root, 'F5', 'F5'); } }});
  await f.connect(); armed = true; down(f.root, 'F5', 'F5'); assert.equal(legacyEdits(f).length, 0);
  down(f.root, 'F5', 'F5'); up(f.root, 'F5', 'F5');
  assert.deepEqual(legacyEdits(f).map(value => value.input.phase), ['down', 'up']); assert.deepEqual(f.errors, []); f.surface.close();
});
test('external packet mutation cannot rewrite the retained trusted body key tuple', async () => {
  const f = bodyFixture('63', {onOperation(operation) { if (operation.input?.kind === 'key' && operation.input.phase === 'down') operation.input.code = 'F6'; }});
  await f.connect(); down(f.root, 'F5', 'F5'); f.setResolver(() => null); f.publish(clone(f.initial));
  up(f.root, 'F5', 'F6'); assert.equal(legacyEdits(f).length, 1);
  up(f.root, 'F5', 'F5'); assert.equal(legacyEdits(f).length, 2); assert.equal(legacyEdits(f)[1].input.key, 'F5');
  assert.deepEqual(f.errors, []); f.surface.close();
});


for (const transitionalFocus of [false, true])
  test(`a held body release reaches only the current focused textarea: transitional=${transitionalFocus}`, async () => {
    const f = bodyFixture(); await f.connect(); down(f.root, 'F5', 'F5');
    if (transitionalFocus) {
      const create = f.document.createElement;
      f.document.createElement = name => { const node = create(name); node.focus = () => {
        const old = f.document.activeElement; f.document.activeElement = null;
        old?.dispatch('focusout', {cancelable: false, relatedTarget: node});
        f.document.activeElement = node; node.dispatch('focusin', {cancelable: false, relatedTarget: old});
      }; return node; };
    }
    const editor = frame(); f.setResolver(() => ({basis: editor.basis, settlement: null})); f.publish(editor);
    const node = f.element(); assert.ok(node); assert.equal(f.document.activeElement, node);
    const focusCount = f.operations.filter(value => value.input?.kind === 'focus' && !value.input.focused).length;
    assert.equal(focusCount, 0); down(node, 'q', 'KeyQ', {ctrlKey: true});
    up(node, 'F5', 'F5'); up(node, 'F5', 'F5');
    assert.deepEqual(legacyEdits(f).map(value => [value.input.phase, value.input.key]), [['down', 'F5'], ['up', 'F5']]);
    assert.equal(f.sent.length, 0); assert.deepEqual(f.errors, []); f.surface.close();
  });
for (const invalid of ['synthetic', 'mismatched-code', 'retired-node', 'foreign-node', 'successor-context'])
  test(`textarea body continuation rejects ${invalid}`, async () => {
    const f = bodyFixture(); await f.connect(); down(f.root, 'F5', 'F5');
    const editor = frame(); f.setResolver(() => ({basis: editor.basis, settlement: null})); f.publish(editor);
    const node = f.element();
    if (invalid === 'retired-node') {
      const successor = frame({token: '700'}); f.setResolver(() => ({basis: successor.basis, settlement: null})); f.publish(successor);
      up(node, 'F5', 'F5');
    } else if (invalid === 'foreign-node') f.document.dispatch('keyup', {key: 'F5', code: 'F5'});
    else if (invalid === 'successor-context') {
      const successor = frame({token: '700', context: '14'}); f.setResolver(() => ({basis: successor.basis, settlement: null})); f.publish(successor);
      up(f.element(), 'F5', 'F5');
    } else up(node, 'F5', invalid === 'mismatched-code' ? 'F6' : 'F5', invalid === 'synthetic' ? {isTrusted: false} : {});
    assert.deepEqual(legacyEdits(f).map(value => value.input.phase), ['down']); assert.deepEqual(f.errors, []); f.surface.close();
  });


for (const textarea of [false, true])
  test(`physical body ownership preserves actual shifted keyup values: textarea=${textarea}`, async () => {
    const f = bodyFixture(); await f.connect(); down(f.root, 'A', 'KeyA', {shiftKey: true});
    let target = f.root;
    if (textarea) { const editor = frame(); f.setResolver(() => ({basis: editor.basis, settlement: null})); f.publish(editor); target = f.element(); }
    else { f.setResolver(() => null); f.publish(clone(f.initial)); }
    up(target, 'a', 'KeyA', {shiftKey: false}); up(target, 'a', 'KeyA');
    const keys = legacyEdits(f); assert.equal(keys.length, 2);
    assert.deepEqual(keys.map(value => [value.input.phase, value.input.key, value.input.code, value.input.modifiers]),
      [['down', 'A', 'KeyA', 1], ['up', 'a', 'KeyA', 0]]);
    assert.deepEqual(f.errors, []); f.surface.close();
  });
for (const collision of ['different-code', 'different-location', 'empty-code-key', 'code-presence'])
  test(`physical body ownership rejects ${collision}`, async () => {
    const f = bodyFixture(); await f.connect();
    const first = collision === 'empty-code-key' ? ['A', ''] : collision === 'code-presence' ? ['KeyA', ''] : ['A', 'KeyA'];
    down(f.root, ...first); f.setResolver(() => null); f.publish(clone(f.initial));
    if (collision === 'different-code') up(f.root, 'A', 'KeyB');
    if (collision === 'different-location') up(f.root, 'A', 'KeyA', {location: 1});
    if (collision === 'empty-code-key') up(f.root, 'a', '');
    if (collision === 'code-presence') up(f.root, 'a', 'KeyA');
    assert.equal(legacyEdits(f).length, 1); up(f.root, ...first); assert.equal(legacyEdits(f).length, 2);
    assert.deepEqual(f.errors, []); f.surface.close();
  });


function admissionPause(f) { f.setResolver(() => ({pending: true})); f.publish(clone(f.initial)); }
test('explicit pending admission preserves the textarea and resumes the same native token with a revision alias', async () => {
  const f = fixture({initial: frame({value: 'abc'})}); await f.connect(); const node = f.element(), original = clone(f.initial);
  admissionPause(f); assert.equal(f.element(), node); assert.equal(node.value, 'abc');
  assert.equal(passage(node, 'x').defaultPrevented, true); await flush(); assert.equal(f.sent.length, 0);
  assert.deepEqual(f.revoked, []); assert.deepEqual(f.resync, []);
  const alias = clone(original); alias.snapshot.revision = '9007199254740994';
  alias.state.presentation.identity.presentationRevision = alias.snapshot.revision; alias.basis.identity.presentationRevision = alias.snapshot.revision;
  f.restoreResolver(); f.publish(alias); assert.equal(f.element(), node); passage(node, 'x'); await flush();
  assert.equal(f.sent.length, 1); assert.equal(f.sent[0].basis.token, original.basis.token);
  assert.equal(f.sent[0].basis.identity.presentationRevision, original.basis.identity.presentationRevision);
  await f.answer(0); healthy(f); f.surface.close();
});
test('pending admission retains the existing bounded predecessor burst without transmission or replay', async () => {
  const f = fixture(); await f.connect(); const node = f.element(); passage(node, 'a'); passage(node, 'b');
  admissionPause(f); await flush(); assert.equal(f.sent.length, 0); assert.equal(node.value, 'ab');
  f.restoreResolver(); f.publish(clone(f.initial)); await flush(); assert.equal(f.sent.length, 1);
  await f.answer(0); assert.equal(f.sent.length, 2); assert.equal(f.sent[1].observation.predecessor, f.sent[0].observation.id);
  assert.equal(f.sent[0].session, f.sent[1].session); await f.answer(1);
  assert.equal(f.element(), node); assert.equal(node.value, 'ab'); assert.equal(f.sent.length, 2); healthy(f); f.surface.close();
});
test('a paused outstanding head needs its checked settlement before queued ingress resumes', async () => {
  const f = fixture(); await f.connect(); const node = f.element(); passage(node, 'a'); await flush();
  admissionPause(f); f.restoreResolver(); f.publish(clone(f.initial));
  assert.equal(passage(node, 'x').defaultPrevented, true); await flush(); assert.equal(f.sent.length, 1);
  await f.answer(0); passage(node, 'b'); await flush(); assert.equal(f.sent.length, 2); await f.answer(1);
  assert.equal(f.element(), node); assert.equal(node.value, 'ab'); healthy(f); f.surface.close();
});
test('an inert pause preserves the checked logical pending IME transaction and native attestation zero', async () => {
  const f = fixture(); await f.connect(); const node = f.element(); node.dispatch('compositionstart', {data: '', cancelable: false}); await flush();
  const transaction = f.sent[0].observation.transaction;
  await f.answer(0, {basis: frame({token: '701', revision: '9007199254741051'}).basis, composition: {transaction, state: 'pending'}});
  admissionPause(f); assert.equal(f.element(), node); assert.equal(f.initial.state.composition, transaction);
  assert.deepEqual(f.revoked, []); assert.deepEqual(f.resync, []);
  f.restoreResolver(); f.publish(clone(f.initial));
  node.dispatch('beforeinput', {inputType: 'insertCompositionText', data: '漢', isComposing: true, cancelable: false});
  node.value = '漢'; node.setSelectionRange(1, 1); node.dispatch('input', {inputType: 'insertCompositionText', data: '漢', isComposing: true, cancelable: false});
  await flush(); assert.equal(f.sent[1].observation.transaction, transaction); assert.equal(f.sent[1].basis.composition, '0');
  await f.answer(1); node.dispatch('compositionend', {data: '漢', cancelable: false}); await flush(); await f.answer(2);
  assert.equal(f.element(), node); assert.equal(node.value, '漢'); healthy(f); f.surface.close();
});
test('actual composition phase during pause retires ambiguity rather than inventing continuity', async () => {
  const f = fixture(); await f.connect(); const node = f.element(); admissionPause(f);
  node.dispatch('compositionstart', {data: '', cancelable: false}); await flush();
  assert.equal(f.element(), null); assert.equal(f.sent.length, 0); assert.equal(f.revoked.length, 1); assert.equal(f.resync.length, 1);
  f.restoreResolver(); f.publish(clone(f.initial)); assert.equal(f.element(), null); f.surface.close();
});
test('changed native facts under the same paused token cannot be upgraded into authority', async () => {
  const f = fixture(); await f.connect(); admissionPause(f);
  const changed = frame({value: 'changed'}); f.restoreResolver(); f.publish(changed);
  assert.equal(f.element(), null); assert.equal(f.revoked.length, 1); assert.equal(f.sent.length, 0);
  f.publish(changed); assert.equal(f.element(), null); assert.deepEqual(f.errors, []); f.surface.close();
});
test('pending publication with a replaced public context performs actual local retirement', async () => {
  const f = fixture(); await f.connect(); admissionPause(f); const next = frame({context: '14'}); f.publish(next);
  assert.equal(f.element(), null); assert.equal(f.revoked.length, 1); assert.equal(f.sent.length, 0); assert.deepEqual(f.errors, []); f.surface.close();
});
test('reentrant pending publication during textarea creation cannot leave admitted input or steal focus', async () => {
  let f, once = false;
  f = fixture({onAppend() { if (!once) { once = true; admissionPause(f); } }}); await f.connect(); const node = f.element();
  assert.ok(node); assert.equal(f.document.activeElement, f.root); assert.deepEqual(f.revoked, []); assert.deepEqual(f.resync, []);
  f.restoreResolver(); f.publish(clone(f.initial)); assert.equal(f.element(), node); assert.equal(f.document.activeElement, node);
  passage(node, 'x'); await flush(); assert.equal(f.sent.length, 1); await f.answer(0); healthy(f); f.surface.close();
});
for (const variant of ['false', 'extra', 'accessor', 'undefined']) test(`pending admission marker is closed and inert: ${variant}`, async () => {
  const f = fixture(); await f.connect(); let reads = 0;
  const marker = variant === 'undefined' ? undefined : variant === 'false' ? {pending: false} : variant === 'extra' ? {pending: true, extra: 1} : {};
  if (variant === 'accessor') Object.defineProperty(marker, 'pending', {enumerable: true, get() { ++reads; return true; }});
  f.setResolver(() => marker); assert.throws(() => f.publish(clone(f.initial)));
  assert.equal(reads, 0); assert.equal(f.element(), null); assert.equal(f.sent.length, 0); f.surface.close();
});
for (const ownObservation of [true, false]) test(`known null retirement preserves the actual ended logical transaction: own=${ownObservation}`, async () => {
  let settled = null; const f = fixture({onResync(reason, basis, metadata) { if (metadata?.settled) settled = metadata.receipt; }});
  await f.connect(); const node = f.element(); node.dispatch('compositionstart', {data: '', cancelable: false}); await flush();
  const transaction = f.sent[0].observation.transaction; let index = 0;
  if (!ownObservation) {
    await f.answer(0, {basis: frame({token: '702', revision: '9007199254741061'}).basis, composition: {transaction, state: 'pending'}});
    down(node, 'ArrowRight', 'ArrowRight'); await flush(); index = 1;
  }
  const packet = f.sent[index], proof = retirementProof(packet.basis, 'available', true);
  nullPublication(f, packet, proof, {redacted: true}); f.deferred[index].resolve({...retirementReceipt(packet, proof), composition: {transaction, state: 'ended'}}); await flush();
  assert.deepEqual(settled?.composition, {transaction, state: 'ended'}); assert.equal(settled.outcome, 'applied');
  assert.equal(f.element(), null); assert.deepEqual(f.errors, []); assert.equal(f.sent.length, index + 1); f.surface.close();
});
for (const phase of ['pending', 'live', 'foreign-ended']) test(`null retirement rejects unproved composition ${phase}`, async () => {
  const f = fixture(); await f.connect(); f.element().dispatch('compositionstart', {data: '', cancelable: false}); await flush();
  const packet = f.sent[0], proof = retirementProof(packet.basis, 'available', true), transaction = packet.observation.transaction;
  f.deferred[0].resolve({...retirementReceipt(packet, proof), composition: {transaction: phase === 'foreign-ended' ? '18446744073709551615' : transaction,
    state: phase === 'foreign-ended' ? 'ended' : phase}}); await flush();
  assert.equal(f.errors.length, 1); assert.equal(f.element(), null); assert.equal(f.revoked.length, 0); assert.equal(f.sent.length, 1);
});
test('noneditable authority-retired proof closes input without granting a fresh body down', async () => {
  const f = bodyFixture(); await f.connect(); down(f.root, 'F5', 'F5'); const closed = clone(f.initial);
  f.setResolver(() => ({basis: null, settlement: null, retirement: retirementProof(closed.basis, 'noneditable', true)})); f.publish(closed);
  down(f.root, 'q', 'KeyQ'); up(f.root, 'F5', 'F5');
  assert.deepEqual(legacyEdits(f).map(value => [value.input.phase, value.input.key]), [['down', 'F5'], ['up', 'F5']]);
  assert.deepEqual(f.errors, []); f.surface.close();
});
