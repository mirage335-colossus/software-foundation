// SPDX-License-Identifier: CC0-1.0
// Production callbacks over an explicit fake DOM and authoritative receipt model.
// isTrusted below is a model flag: no browser, native IME or engine executes.
import assert from 'node:assert/strict';
import test from 'node:test';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';

const {createBrowserEditorConduit} = await import(process.argv[2]
  ? pathToFileURL(resolve(process.argv[2])).href : new URL('../host/browser_surface_editor.mjs', import.meta.url).href);
const encoder = new TextEncoder(), wide = '9007199254740993';
const flush = () => new Promise(resolve => setImmediate(resolve));
const bytes = text => encoder.encode(text).length;
const basis = ({value = '', first = value.length, last = first, backward = false, token = wide,
  revision = wide, composition = '0', context = '7'} = {}) => ({
  token, editorRevision: revision, surrounding: value,
  selection: [bytes(value.slice(0, first)), bytes(value.slice(0, last))], backward, composition,
  identity: {owner: {id: 'editor', generation: wide}, presentationRevision: wide,
    generation: '5', epoch: '6', context}
});

class FakeTarget {
  listeners = new Map();
  addEventListener(type, listener, options) {
    const entries = this.listeners.get(type) ?? [];
    entries.push({listener, options}); this.listeners.set(type, entries);
  }
  removeEventListener(type, listener) {
    this.listeners.set(type, (this.listeners.get(type) ?? []).filter(entry => entry.listener !== listener));
  }
  emit(type, values = {}) {
    const event = {type, target: this, isTrusted: true, cancelable: true, defaultPrevented: false,
      isComposing: false, key: '', code: '', location: 0, repeat: false,
      shiftKey: false, ctrlKey: false, altKey: false, metaKey: false,
      getModifierState: () => false,
      preventDefault() { if (this.cancelable) this.defaultPrevented = true; },
      stopImmediatePropagation() { this.stopped = true; }, ...values};
    for (const {listener} of [...(this.listeners.get(type) ?? [])]) {
      listener(event); if (event.stopped) break;
    }
    return event;
  }
  listenerCount() { return [...this.listeners.values()].reduce((count, entries) => count + entries.length, 0); }
}

class FakeTextarea extends FakeTarget {
  constructor(document) {
    super(); this.document = document; this.style = {}; this.attributes = new Map(); this._value = '';
    this.selectionStart = this.selectionEnd = 0; this.selectionDirection = 'none'; this.removed = false;
  }
  setAttribute(name, value) { this.attributes.set(name, value); }
  get value() { return this._value; }
  set value(value) {
    const next = this.document.normalizeNewlines ? value.replace(/\r\n?/g, '\n') : value;
    if (next === this._value) return;
    this._value = next; this.selectionStart = this.selectionEnd = next.length; this.selectionDirection = 'none';
    this.document.queueSelection(this);
  }
  setSelectionRange(first, last, direction = 'none') {
    first = Math.min(this.value.length, Math.max(0, first)); last = Math.min(this.value.length, Math.max(0, last));
    if (last <= first) first = last;
    const nextDirection = ['forward', 'backward'].includes(direction) ? direction : 'none';
    const changed = first !== this.selectionStart || last !== this.selectionEnd || nextDirection !== this.selectionDirection;
    this.selectionStart = first; this.selectionEnd = last; this.selectionDirection = nextDirection;
    if (changed) this.document.queueSelection(this);
  }
  focus() {
    const previous = this.document.activeElement;
    this.document.activeElement = this;
    if (previous && previous !== this) previous.emit('blur');
  }
  remove() {
    this.removed = true;
    const index = this.parent?.children.indexOf(this) ?? -1;
    if (index >= 0) this.parent.children.splice(index, 1);
    if (this.document.activeElement === this) this.document.activeElement = null;
  }
}

class FakeDocument {
  activeElement = null;
  selectionTasks = new Set();
  constructor({normalizeNewlines = true} = {}) { this.normalizeNewlines = normalizeNewlines; }
  createElement(tag) { assert.equal(tag, 'textarea'); return new FakeTextarea(this); }
  queueSelection(node) { this.selectionTasks.add(node); }
  flushSelection() {
    const nodes = [...this.selectionTasks]; this.selectionTasks.clear();
    for (const node of nodes) node.emit('selectionchange', {cancelable: false});
  }
}

function fixture(options = {}) {
  const document = new FakeDocument(options), root = {children: [],
    appendChild(node) { node.parent = this; this.children.push(node); options.onAppend?.(node); },
    getBoundingClientRect: () => ({left: 10, top: 20, width: 640, height: 480})};
  const sent = [], deferred = [], failures = [], resync = [], revoked = [], traces = [];
  let actual = options.initial ?? basis(), receiptSerial = 0n;
  const conduit = createBrowserEditorConduit({root, document,
    send(packet) { sent.push(packet); return new Promise((resolve, reject) => deferred.push({resolve, reject})); },
    onFailure: error => { failures.push(error); options.onFailure?.(error); },
    onResync: (reason, accepted, metadata) => { resync.push({reason, accepted}); options.onResync?.(reason, accepted, metadata); },
    onRevoke: value => { revoked.push(value); options.onRevoke?.(value); }, onTrace: value => traces.push(value),
    ...(options.maxPending === undefined ? {} : {maxPending: options.maxPending}),
    ...(options.maxBytes === undefined ? {} : {maxBytes: options.maxBytes})});
  const publish = (next = actual, settings = {}) => {
    const accepted = conduit.publish(next, {focused: true, active: true, editable: true, caret: [3, 4, 1, 15], ...settings});
    if (accepted) actual = next;
    return accepted;
  };
  if (options.publish !== false) assert.equal(publish(), true);
  const answer = async (index, changes = {}) => {
    assert.ok(sent[index], `Expected observation ${index}`);
    const packet = sent[index], observation = packet.observation;
    if (changes.outcome === 'unknown') {
      const receipt = {session: packet.session, id: observation.id, predecessor: observation.predecessor,
        submittedToken: packet.basis.token, outcome: 'unknown'};
      deferred[index].resolve(receipt); await flush(); return receipt;
    }
    // A late old flight remains an old owner's reply even after publication
    // installs a successor session. Never manufacture cross-context continuity.
    const owner = packet.session === conduit.state().session ? actual : packet.basis;
    let next = changes.basis;
    if (!next) {
      const capture = observation.kind === 'key' ? null : observation.after;
      const ending = observation.kind === 'composition' && ['commit', 'cancel'].includes(observation.data.operation);
      const composition = observation.kind === 'composition' ? ending ? '0' : observation.transaction : owner.composition;
      next = basis({value: capture?.value ?? owner.surrounding,
        first: capture?.selectionStart ?? (() => {
          // Convert only the model owner's accepted byte selection to UTF-16.
          let offset = 0, total = 0; for (const character of owner.surrounding) {
            if (total === owner.selection[0]) break; total += bytes(character); offset += character.length;
          } return offset;
        })(),
        last: capture?.selectionEnd ?? (() => {
          let offset = 0, total = 0; for (const character of owner.surrounding) {
            if (total === owner.selection[1]) break; total += bytes(character); offset += character.length;
          } return offset;
        })(),
        backward: capture ? capture.selectionDirection === 'backward' : owner.backward,
        token: String(1000n + ++receiptSerial), revision: String(10000000000000000n + receiptSerial * 17n),
        composition, context: owner.identity.context});
    }
    let composition = null;
    if (observation.kind === 'composition') composition = {transaction: observation.transaction,
      state: ['commit', 'cancel'].includes(observation.data.operation) ? 'ended' : 'live'};
    else if (owner.composition !== '0') composition = {transaction: owner.composition, state: 'live'};
    const defaultToken = observation.kind === 'key' && observation.data.phase === 'down' && observation.group !== null ?
      {token: String(8000 + index), group: observation.group} : null;
    const receipt = {session: packet.session, id: observation.id, predecessor: observation.predecessor,
      submittedToken: packet.basis.token, outcome: 'applied', basis: next, continuity: 'same', defaultToken, composition, ...changes};
    if (packet.session === conduit.state().session) actual = receipt.basis;
    deferred[index].resolve(receipt); await flush(); return receipt;
  };
  return {document, root, conduit, publish, sent, deferred, failures, resync, revoked, traces, answer,
    async finish() { await flush(); for (let index = 0; index < sent.length; ++index) await answer(index); },
    get actual() { return actual; }};
}

const down = (node, key = 'a', code = 'KeyA', values = {}) => node.emit('keydown', {key, code, ...values});
const up = (node, key = 'a', code = 'KeyA', values = {}) => node.emit('keyup', {key, code, ...values});
function passage(node, text, {inputType = 'insertText', isComposing = false} = {}) {
  const event = node.emit('beforeinput', {inputType, data: text, isComposing});
  if (!event.defaultPrevented) {
    const first = node.selectionStart, last = node.selectionEnd;
    node.value = node.value.slice(0, first) + text + node.value.slice(last);
    node.setSelectionRange(first + text.length, first + text.length);
    node.emit('input', {inputType, data: text, isComposing, cancelable: false});
  }
  return event;
}
function preedit(node, text, value, position, order) {
  const input = {inputType: 'insertCompositionText', data: text, isComposing: true, cancelable: false};
  if (order === 'update-first') node.emit('compositionupdate', {data: text, cancelable: false});
  node.emit('beforeinput', input);
  if (order === 'beforeinput-first') node.emit('compositionupdate', {data: text, cancelable: false});
  node.value = value; node.setSelectionRange(position, position);
  node.emit('input', input);
}
function healthy(f) { assert.deepEqual(f.failures, []); assert.deepEqual(f.resync, []); }

test('publication creates one caret-positioned native conduit and exact scalar selection', () => {
  const f = fixture({initial: basis({value: 'aé😀z', first: 1, last: 4, backward: true})});
  const node = f.conduit.element();
  assert.equal(f.root.children.length, 1); assert.equal(f.document.activeElement, node);
  assert.equal(node.value, 'aé😀z'); assert.deepEqual([node.selectionStart, node.selectionEnd, node.selectionDirection], [1, 4, 'backward']);
  assert.equal(node.attributes.get('aria-label'), 'Application text input'); assert.notEqual(node.style.display, 'none');
  assert.equal(node.style.left, '13px'); assert.equal(node.style.top, '24px');
  f.document.flushSelection(); assert.equal(f.sent.length, 0); healthy(f); f.conduit.close();
});

test('caret placement clips native coordinates to the published visible root region', () => {
  const f = fixture({publish: false});
  assert.equal(f.publish(basis(), {caret: [1000, -100, 1, 15], clip: [5, 8, 20, 10]}), true);
  assert.equal(f.conduit.element().style.left, '34px'); assert.equal(f.conduit.element().style.top, '28px');
  healthy(f); f.conduit.close();
});

test('native typing bursts retain real provisional values while owner receipts supply revisions and default tokens', async () => {
  const f = fixture(), node = f.conduit.element();
  down(node); assert.equal(passage(node, 'a').defaultPrevented, false); up(node);
  down(node, 'b', 'KeyB'); passage(node, 'b'); up(node, 'b', 'KeyB');
  assert.equal(node.value, 'ab'); await flush(); assert.equal(f.sent.length, 1); assert.equal(f.conduit.state().pending, 6);
  for (let index = 0; index < 6; ++index) {
    await f.answer(index); if (index < 5) assert.equal(node.value, 'ab', 'pending native passage must not be rewritten');
  }
  assert.deepEqual(f.sent.map(packet => packet.observation.kind), ['key', 'text', 'key', 'key', 'text', 'key']);
  assert.deepEqual(f.sent.filter(packet => packet.observation.kind === 'text').map(packet => packet.observation.before.value), ['', 'a']);
  for (const packet of f.sent.filter(packet => packet.observation.kind === 'text')) {
    assert.equal(packet.observation.authority, 'default'); assert.ok(packet.defaultToken);
    assert.equal(Object.hasOwn(packet.observation, 'editorRevision'), false);
  }
  assert.equal(f.sent[1].basis.editorRevision, '10000000000000017');
  assert.equal(f.sent[4].observation.predecessor, f.sent[3].observation.id);
  assert.equal(f.conduit.state().pending, 0); assert.equal(node.value, 'ab'); healthy(f); f.conduit.close();
});

test('owner cancellation retires the provisional tail instead of exporting its text or replaying it', async () => {
  const f = fixture(), old = f.conduit.element(); down(old); passage(old, 'a'); up(old); await flush();
  await f.answer(0, {outcome: 'cancelled', basis: basis({token: '41'}), defaultToken: null});
  assert.equal(f.sent.length, 1); assert.equal(f.conduit.state().status, 'suspended'); assert.equal(f.conduit.element(), null);
  assert.equal(old.listenerCount(), 0); assert.equal(f.revoked.length, 1); assert.match(f.resync[0].reason, /cancelled/i);
  down(old, 'z', 'KeyZ'); passage(old, 'z'); await flush(); assert.equal(f.sent.length, 1); assert.deepEqual(f.failures, []);
});

test('an applied raw key without an owner-issued continuation never authorizes queued text', async () => {
  const f = fixture(), node = f.conduit.element(); down(node); passage(node, 'a'); await flush();
  await f.answer(0, {defaultToken: null});
  assert.equal(f.sent.length, 1); assert.equal(f.conduit.state().status, 'suspended');
  assert.match(f.resync[0].reason, /not authorized/i); assert.equal(f.conduit.element(), null); assert.deepEqual(f.failures, []);
});

test('native key payload bounds count UTF-8 bytes rather than UTF-16 units', async () => {
  const accepted = fixture(), node = accepted.conduit.element(), boundary = '😀'.repeat(16);
  down(node, boundary, 'KeyA'); up(node, boundary, 'KeyA'); await accepted.finish();
  assert.equal(bytes(accepted.sent[0].observation.data.key), 64); healthy(accepted); accepted.conduit.close();
  const rejected = fixture(); down(rejected.conduit.element(), '😀'.repeat(17), 'KeyA'); await flush();
  assert.equal(rejected.sent.length, 0); assert.equal(rejected.conduit.element(), null);
  assert.equal(rejected.conduit.state().status, 'suspended'); assert.equal(rejected.resync[0].reason, 'Invalid editor text observation');
  assert.deepEqual(rejected.failures, []);
});

test('a Dead key prefix and base key require both actual owner continuations for one native text passage', async () => {
  const f = fixture(), node = f.conduit.element();
  down(node, 'Dead', 'Quote'); up(node, 'Dead', 'Quote');
  down(node, 'e', 'KeyE'); passage(node, 'é'); up(node, 'e', 'KeyE');
  assert.equal(node.value, 'é'); await flush(); assert.equal(f.sent.length, 1);
  for (let index = 0; index < 3; ++index) await f.answer(index);
  assert.deepEqual(f.sent.map(packet => packet.observation.kind), ['key', 'key', 'key', 'text']);
  const [deadDown, deadUp, baseDown, text] = f.sent;
  assert.equal(deadUp.observation.group, deadDown.observation.group); assert.equal(deadUp.observation.groupEnd, false);
  assert.deepEqual(text.observation.data.sourceGroups, [deadDown.observation.group, baseDown.observation.group]);
  assert.deepEqual(text.defaultDependencies, [
    {group: deadDown.observation.group, token: '8000'}, {group: baseDown.observation.group, token: '8002'}]);
  assert.equal(text.defaultToken, '8002'); assert.equal(text.observation.before.value, '');
  assert.equal(text.observation.after.value, 'é'); assert.equal(text.observation.data.text, 'é');
  await f.answer(3); await f.answer(4); assert.equal(node.value, 'é'); healthy(f); f.conduit.close();
});

for (const outcome of ['applied', 'cancelled']) test(`a ${outcome === 'applied' ? 'missing' : 'cancelled'} Dead continuation never exports final native text`, async () => {
  const f = fixture(), node = f.conduit.element();
  down(node, 'Dead', 'Quote'); up(node, 'Dead', 'Quote');
  down(node, 'e', 'KeyE'); passage(node, 'é'); up(node, 'e', 'KeyE'); await flush();
  await f.answer(0, {outcome, defaultToken: null});
  if (outcome === 'applied') { await f.answer(1); await f.answer(2); }
  assert.equal(f.sent.length, outcome === 'applied' ? 3 : 1);
  assert.equal(f.sent.some(packet => packet.observation.kind === 'text'), false);
  assert.equal(f.conduit.state().status, 'suspended'); assert.equal(f.conduit.element(), null);
  assert.match(f.resync[0].reason, outcome === 'applied' ? /not authorized/i : /cancelled/i); assert.deepEqual(f.failures, []);
});

test('captured Backspace performs only the native key command and no duplicate text edit', async () => {
  const f = fixture({initial: basis({value: 'ab'})}), node = f.conduit.element();
  assert.equal(down(node, 'Backspace', 'Backspace').defaultPrevented, true); up(node, 'Backspace', 'Backspace');
  await flush(); await f.answer(0, {basis: basis({value: 'a', token: '51', revision: '300'})}); await f.answer(1);
  assert.deepEqual(f.sent.map(packet => packet.observation.kind), ['key', 'key']); assert.equal(node.value, 'a'); healthy(f); f.conduit.close();
});

test('an unexpected UA deletion after captured Backspace retires instead of duplicating the native edit', async () => {
  const f = fixture({initial: basis({value: 'ab'})}), node = f.conduit.element();
  down(node, 'Backspace', 'Backspace'); await flush();
  const event = node.emit('beforeinput', {inputType: 'deleteContentBackward', data: null});
  assert.equal(event.defaultPrevented, true); assert.equal(f.conduit.element(), null);
  assert.equal(f.sent.length, 1); assert.equal(f.sent[0].observation.kind, 'key'); assert.deepEqual(f.failures, []);
});

test('a source-qualified text default uses the owner post-key target while preserving its proxy observation', async () => {
  const f = fixture({initial: basis({value: 'abc'})}), node = f.conduit.element(); down(node, 'X', 'KeyX'); passage(node, 'X'); up(node, 'X', 'KeyX');
  await flush(); await f.answer(0, {basis: basis({value: 'abc', first: 0, context: '88', token: '61', revision: '401'}), continuity: 'key-retarget'});
  assert.equal(f.sent[1].basis.identity.context, '88'); assert.deepEqual(f.sent[1].basis.selection, [0, 0]);
  assert.equal(f.sent[1].observation.before.selectionStart, 3); assert.equal(f.sent[1].observation.after.value, 'abcX'); assert.ok(f.sent[1].defaultToken);
  await f.answer(1, {basis: basis({value: 'Xabc', context: '88', token: '62', revision: '433'})}); await f.answer(2);
  assert.equal(node.value, 'Xabc'); assert.equal(f.root.children.length, 1); healthy(f); f.conduit.close();
});

for (const order of ['update-first', 'beforeinput-first']) test(`native IME ${order} queues begin, updates and one terminal without rewriting preedit`, async () => {
  const f = fixture({initial: basis({value: 'abc', first: 1, last: 2})}), node = f.conduit.element();
  node.emit('compositionstart', {data: '', cancelable: false});
  preedit(node, 'é', 'aéc', 2, order); preedit(node, '😀', 'a😀c', 3, order);
  node.emit('compositionend', {data: '😀', cancelable: false});
  const duplicate = node.emit('beforeinput', {inputType: 'insertFromComposition', data: '😀'});
  assert.equal(duplicate.defaultPrevented, true);
  node.emit('input', {inputType: 'insertFromComposition', data: '😀', cancelable: false});
  await flush(); assert.equal(f.sent.length, 1); assert.equal(f.conduit.state().pending, 4);
  for (let index = 0; index < 4; ++index) { await f.answer(index); assert.equal(node.value, 'a😀c'); }
  assert.deepEqual(f.sent.map(packet => packet.observation.data.operation), ['begin', 'update', 'update', 'commit']);
  assert.deepEqual(f.sent[2].observation.data.selection, [4, 4]); assert.equal(f.sent[3].observation.transaction, f.sent[0].observation.transaction);
  assert.equal(f.conduit.state().basis.composition, '0'); assert.equal(f.conduit.state().pending, 0); healthy(f); f.conduit.close();
});

for (const type of ['beforeinput', 'input']) test(`only one exact terminal ${type} duplicate is locally consumed`, async () => {
  const f = fixture(), node = f.conduit.element(); node.emit('compositionstart', {data: '', cancelable: false});
  preedit(node, 'é', 'é', 1, 'update-first'); node.emit('compositionend', {data: 'é', cancelable: false});
  await f.finish(); healthy(f); const count = f.sent.length;
  node.emit(type, {inputType: 'insertFromComposition', data: 'é', cancelable: type === 'beforeinput'});
  assert.equal(f.conduit.element(), node); assert.equal(f.sent.length, count);
  node.emit(type, {inputType: 'insertFromComposition', data: 'é', cancelable: type === 'beforeinput'});
  await flush(); assert.equal(f.conduit.element(), null); assert.equal(f.sent.length, count);
  assert.match(f.resync[0].reason, /duplicate terminal/i); assert.deepEqual(f.failures, []);
});

test('IME activation can consume a raw Process default token while later updates use composition authority', async () => {
  const f = fixture(), node = f.conduit.element(); down(node, 'Process', 'KeyA');
  node.emit('compositionstart', {data: '', cancelable: false}); up(node, 'Process', 'KeyA', {isComposing: true});
  preedit(node, '漢', '漢', 1, 'update-first'); node.emit('compositionend', {data: '漢', cancelable: false});
  await f.finish(); assert.deepEqual(f.sent.map(packet => packet.observation.kind), ['key', 'composition', 'key', 'composition', 'composition']);
  assert.equal(f.sent[1].observation.authority, 'default'); assert.ok(f.sent[1].defaultToken);
  assert.equal(f.sent[3].observation.authority, 'composition'); assert.equal(f.sent[3].defaultToken, null);
  assert.equal(node.value, '漢'); healthy(f); f.conduit.close();
});

for (const [label, data] of [
  ['overlong ASCII', 'x'.repeat(65537)],
  ['UTF-8 byte overflow within the UTF-16 bound', 'é'.repeat(32769)],
  ['unpaired surrogate', '\uD800'],
  ['object instead of nullable string', {text: 'preedit'}]
]) test(`composition beforeinput rejects ${label} before retaining a pending passage`, async () => {
  const f = fixture(), node = f.conduit.element(); node.emit('compositionstart', {data: '', cancelable: false});
  await flush(); assert.equal(f.sent.length, 1);
  node.emit('beforeinput', {inputType: 'insertCompositionText', data, isComposing: true, cancelable: false});
  assert.equal(f.conduit.state().status, 'suspended'); assert.equal(f.conduit.element(), null);
  assert.equal(node.listenerCount(), 0); assert.equal(f.resync.length, 1); assert.equal(f.revoked.length, 1);
  node.value = 'late'; node.emit('input', {inputType: 'insertCompositionText', data: 'late', isComposing: true, cancelable: false});
  await f.answer(0); assert.equal(f.sent.length, 1); assert.equal(f.conduit.element(), null); assert.deepEqual(f.failures, []);
});

test('null composition beforeinput data permits the separately captured actual preedit passage', async () => {
  const f = fixture(), node = f.conduit.element(); node.emit('compositionstart', {data: '', cancelable: false});
  node.emit('beforeinput', {inputType: 'insertCompositionText', data: null, isComposing: true, cancelable: false});
  assert.equal(f.conduit.element(), node);
  node.value = '漢'; node.setSelectionRange(1, 1);
  node.emit('input', {inputType: 'insertCompositionText', data: null, isComposing: true, cancelable: false});
  node.emit('compositionend', {data: '漢', cancelable: false}); await f.finish();
  assert.deepEqual(f.sent.map(packet => packet.observation.data.operation), ['begin', 'update', 'commit']);
  assert.equal(f.sent[1].observation.data.text, '漢'); assert.equal(node.value, '漢'); healthy(f); f.conduit.close();
});

test('empty compositionend without a proved cancellation retires and ignores late begin receipts', async () => {
  const f = fixture(), old = f.conduit.element(); old.emit('compositionstart', {data: '', cancelable: false});
  preedit(old, 'a', 'a', 1, 'beforeinput-first'); await flush();
  old.emit('compositionend', {data: '', cancelable: false}); assert.equal(f.conduit.element(), null);
  assert.match(f.resync[0].reason, /ambiguous empty/i); await f.answer(0);
  assert.equal(f.sent.length, 1); assert.equal(f.conduit.element(), null); assert.deepEqual(f.failures, []);
});

test('explicit Escape cancellation carries one canonical cancel after the actual native rollback', async () => {
  const f = fixture(), node = f.conduit.element(); node.emit('compositionstart', {data: '', cancelable: false});
  preedit(node, 'a', 'a', 1, 'update-first'); down(node, 'Escape', 'Escape', {isComposing: true});
  node.value = ''; node.setSelectionRange(0, 0); node.emit('compositionend', {data: '', cancelable: false}); up(node, 'Escape', 'Escape');
  await f.finish(); const cancels = f.sent.filter(packet => packet.observation.data.operation === 'cancel');
  assert.equal(cancels.length, 1); assert.deepEqual(cancels[0].observation.data, {operation: 'cancel', text: '', selection: [0, 0]});
  assert.equal(node.value, ''); healthy(f); f.conduit.close();
});

test('programmatic selection notifications do not loop while a real changed scalar selection is ordered', async () => {
  const f = fixture({initial: basis({value: 'a😀z', first: 1, last: 3, backward: true})}), node = f.conduit.element();
  f.document.flushSelection(); await flush(); assert.equal(f.sent.length, 0);
  node.setSelectionRange(0, 1, 'forward'); f.document.flushSelection(); await flush(); assert.equal(f.sent.length, 1);
  assert.equal(f.sent[0].observation.kind, 'selection'); assert.deepEqual(f.sent[0].observation.data, {selection: [0, 1], backward: false});
  await f.answer(0); f.document.flushSelection(); await flush(); assert.equal(f.sent.length, 1); healthy(f); f.conduit.close();
});

test('untrusted callbacks, another target and an unfocused element grant no observation authority', async () => {
  const f = fixture(), node = f.conduit.element(), other = f.document.createElement('textarea');
  for (const type of ['keydown', 'keyup', 'beforeinput', 'input', 'compositionstart', 'compositionupdate', 'compositionend', 'selectionchange']) {
    node.emit(type, {isTrusted: false, key: 'a', code: 'KeyA', data: 'a', inputType: 'insertText'});
    node.emit(type, {target: other, key: 'a', code: 'KeyA', data: 'a', inputType: 'insertText'});
  }
  f.document.activeElement = other; down(node); node.emit('compositionstart', {data: ''});
  await flush(); assert.equal(f.sent.length, 0); assert.equal(f.conduit.state().status, 'ready'); healthy(f); f.conduit.close();
});

test('native focus loss removes listeners and late work cannot touch the next textarea incarnation', async () => {
  const f = fixture(), old = f.conduit.element(); down(old); passage(old, 'a'); await flush();
  f.document.activeElement = null; old.emit('blur', {cancelable: false}); assert.equal(f.conduit.element(), null); assert.equal(old.listenerCount(), 0);
  assert.equal(f.publish(basis({value: 'next', token: '71', context: '90'})), true); const next = f.conduit.element();
  down(old, 'z', 'KeyZ'); passage(old, 'z'); await f.answer(0);
  assert.equal(f.conduit.element(), next); assert.equal(next.value, 'next'); assert.equal(f.sent.length, 1);
  assert.equal(f.conduit.state().basis.identity.context, '90'); assert.deepEqual(f.failures, []); f.conduit.close();
});

test('service ownership revokes pending input and a late receipt cannot restore its conduit', async () => {
  const f = fixture(), old = f.conduit.element(); down(old); passage(old, 'a'); await flush();
  assert.equal(f.publish(f.actual, {serviceActive: true}), false); assert.equal(f.conduit.element(), null);
  await f.answer(0); assert.equal(f.conduit.element(), null); assert.equal(f.sent.length, 1);
  assert.equal(f.conduit.state().status, 'suspended'); assert.deepEqual(f.failures, []);
});

test('context replacement owns a new element and waits for the old flight without importing its result', async () => {
  const f = fixture(), old = f.conduit.element(); down(old); passage(old, 'a'); await flush();
  assert.equal(f.publish(basis({value: 'B', token: '81', context: '91'})), true); const next = f.conduit.element();
  assert.notEqual(next, old); assert.equal(old.listenerCount(), 0); assert.equal(f.revoked.at(-1).basis.identity.context, '7');
  passage(next, 'x'); await flush(); assert.equal(f.sent.length, 1);
  await f.answer(0); assert.equal(f.sent.length, 2); assert.equal(f.sent[1].basis.identity.context, '91'); assert.equal(next.value, 'Bx');
  await f.answer(1); assert.equal(next.value, 'Bx'); assert.equal(f.conduit.state().pending, 0); healthy(f); f.conduit.close();
});

test('an authoritative unfocused publication stops callbacks even if its old node was focused', async () => {
  const f = fixture(), old = f.conduit.element(); f.publish(f.actual, {focused: false});
  down(old); passage(old, 'a'); await flush(); assert.equal(f.sent.length, 0);
  assert.equal(f.conduit.element(), null); assert.equal(f.conduit.state().status, 'suspended'); assert.deepEqual(f.failures, []);
});

test('caret validation rejects nonfinite or negative geometry without leaving a live element', () => {
  for (const caret of [[NaN, 0, 1, 1], [0, Infinity, 1, 1], [0, 0, -1, 1], [0, 0, 1, -1]]) {
    const f = fixture({publish: false}); assert.equal(f.publish(basis(), {caret}), false);
    assert.equal(f.conduit.element(), null); assert.equal(f.root.children.length, 0); assert.match(f.resync.at(-1).reason, /caret/i);
  }
});

test('CR and CRLF fail exact textarea API roundtrip while LF remains an exact projection', () => {
  for (const value of ['a\rb', 'a\r\nb']) {
    const f = fixture({publish: false}); assert.equal(f.publish(basis({value})), false);
    assert.equal(f.conduit.element(), null); assert.equal(f.root.children.length, 0); assert.match(f.resync[0].reason, /round-trip/i);
  }
  const f = fixture({initial: basis({value: 'a\nb', first: 2})}); assert.equal(f.conduit.element().selectionStart, 2);
  assert.equal(f.conduit.element().value, 'a\nb'); healthy(f); f.conduit.close();
});

test('a native UTF-16 surrogate-middle selection retires before any text observation', async () => {
  const f = fixture({initial: basis({value: '😀'})}), node = f.conduit.element(); node.setSelectionRange(1, 1);
  node.emit('beforeinput', {inputType: 'insertText', data: 'x'}); await flush();
  assert.equal(f.sent.length, 0); assert.equal(f.conduit.element(), null); assert.match(f.resync[0].reason, /boundary/i);
});

for (const limit of [{maxPending: 1}, {maxBytes: 100}]) test(`bounded observation exhaustion retires without replay: ${JSON.stringify(limit)}`, async () => {
  const f = fixture(limit), node = f.conduit.element(); down(node); if (f.conduit.element()) passage(node, 'a'); await flush();
  assert.equal(f.conduit.state().status, 'suspended'); assert.equal(f.conduit.element(), null);
  assert.equal(f.sent.length, 0); assert.match(f.resync[0].reason, /exhausted/i); assert.deepEqual(f.failures, []);
});

test('close during an unresolved flight forbids late publication, new listeners and later sends', async () => {
  const f = fixture(), old = f.conduit.element(); down(old); passage(old, 'a'); await flush(); f.conduit.close();
  assert.equal(f.conduit.state().status, 'closed'); assert.equal(old.listenerCount(), 0); assert.equal(f.conduit.element(), null);
  await f.answer(0); down(old, 'z', 'KeyZ'); passage(old, 'z'); await flush();
  assert.equal(f.publish(basis({token: '99'})), false); assert.equal(f.sent.length, 1); assert.equal(f.root.children.length, 0);
  assert.deepEqual(f.failures, []);
});

test('onRevoke may close the endpoint without the stale publication creating or focusing a textarea', () => {
  let f;
  f = fixture({onRevoke() { f.conduit.close(); }}); const old = f.conduit.element();
  assert.equal(f.publish(basis({value: 'stale outer', token: '301', context: '301'})), false);
  assert.equal(f.conduit.state().status, 'closed'); assert.equal(f.conduit.element(), null);
  assert.equal(f.root.children.length, 0); assert.equal(f.document.activeElement, null); assert.equal(old.listenerCount(), 0);
  assert.equal(f.revoked.length, 1); assert.deepEqual(f.failures, []);
});

test('onRevoke recursive publication keeps the inner owner and never creates a stale outer incarnation', () => {
  let f, entered = false;
  f = fixture({onRevoke() {
    if (entered) return;
    entered = true; assert.equal(f.publish(basis({value: 'inner', token: '303', context: '303'})), true);
  }});
  assert.equal(f.publish(basis({value: 'stale outer', token: '302', context: '302'})), false);
  assert.equal(f.conduit.element().value, 'inner'); assert.equal(f.root.children.length, 1);
  assert.equal(f.document.activeElement, f.conduit.element()); assert.equal(f.conduit.state().basis.identity.context, '303');
  assert.equal(f.actual.identity.context, '303'); healthy(f); f.conduit.close();
});

for (const throwing of [false, true]) test(`unknown consumed outcome tears down locally without owner cleanup${throwing ? ' even if onFailure throws' : ''}`, async () => {
  const f = fixture({onFailure() { if (throwing) throw Error('Diagnostic callback failed'); }}), old = f.conduit.element();
  const initial = f.actual; down(old); passage(old, 'a'); up(old); await flush(); const unresolved = f.sent[0];
  await f.answer(0, {outcome: 'unknown', defaultToken: null});
  assert.equal(f.conduit.element(), null); assert.equal(old.listenerCount(), 0); assert.equal(f.root.children.length, 0);
  assert.equal(f.revoked.length, 0); assert.deepEqual(f.resync, []); assert.equal(f.failures.length, 1);
  assert.ok(['terminal_unknown', 'closed'].includes(f.conduit.state().status)); assert.deepEqual(f.conduit.state().unresolved, unresolved);
  assert.deepEqual(f.conduit.state().basis, initial); assert.deepEqual(f.actual, initial);
  assert.equal(f.publish(basis({token: '304', context: '304'})), false);
  down(old, 'z', 'KeyZ'); passage(old, 'z'); await flush(); assert.equal(f.sent.length, 1);
});

// Known-null successor: only a checked native retirement removes the old local
// passage with owner notification. These are model receipts, not native proof.
const nullAnswer = (f, index, changes = {}) => f.answer(index, {outcome: 'cancelled', basis: null,
  continuity: 'replaced', defaultToken: null, composition: null,
  retirement: {availability: 'noneditable', identity: structuredClone(f.sent[index].basis.identity),
    observationRevision: '18446744073709551615', readbackAttested: true}, ...changes});

for (const outcome of ['applied', 'cancelled', 'rejected']) for (const availability of ['noneditable', 'unavailable'])
  test(`${outcome} checked ${availability} retirement removes the exact held-key incarnation`, async () => {
    let metadata;
    const f = fixture({onResync(reason, accepted, value) { assert.equal(accepted, null); metadata = value; }});
    const initial = f.actual, old = f.conduit.element(); down(old); passage(old, 'a'); await flush();
    const receipt = await nullAnswer(f, 0, {outcome, retirement: {availability,
      identity: structuredClone(f.sent[0].basis.identity), observationRevision: '1', readbackAttested: true}});
    assert.equal(f.conduit.state().status, 'suspended'); assert.equal(f.conduit.state().basis, null);
    assert.equal(f.conduit.state().pending, 0); assert.equal(f.conduit.state().bytes, 0);
    assert.equal(f.conduit.element(), null); assert.equal(old.listenerCount(), 0); assert.equal(old.removed, true);
    assert.equal(f.root.children.length, 0); assert.equal(f.document.activeElement, null);
    assert.equal(f.revoked.length, 1); assert.equal(f.revoked[0].basis.token, initial.token);
    assert.equal(f.revoked[0].incarnation, '1'); assert.equal(f.revoked[0].keys.length, 1);
    assert.equal(f.revoked[0].keys[0].key, 'a'); assert.equal(f.revoked[0].composition, null);
    assert.deepEqual(f.resync, [{reason: `Editor ${outcome}`, accepted: null}]); assert.deepEqual(f.failures, []);
    assert.equal(metadata.settled, true); assert.deepEqual(metadata.receipt, receipt);
    for (const value of [metadata, metadata.receipt, metadata.receipt.retirement,
      metadata.receipt.retirement.identity, metadata.receipt.retirement.identity.owner]) assert.equal(Object.isFrozen(value), true);
    down(old, 'z', 'KeyZ'); passage(old, 'z'); old.emit('compositionstart'); old.emit('selectionchange'); await flush();
    assert.equal(f.sent.length, 1); f.conduit.retire(); f.conduit.close(); assert.equal(f.revoked.length, 1);
  });

test('known null retirement clears live preedit and queued updates without synthesizing cancellation', async () => {
  const f = fixture(), old = f.conduit.element(); old.emit('compositionstart'); await flush(); await f.answer(0);
  const accepted = f.actual; down(old, 'Process', ''); preedit(old, 'é', 'é', 1, 'update-first'); await flush();
  assert.equal(f.sent.length, 2); assert.equal(f.sent[1].observation.kind, 'key');
  await nullAnswer(f, 1);
  assert.equal(f.sent.length, 2); assert.equal(f.conduit.element(), null); assert.equal(f.conduit.state().basis, null);
  assert.equal(f.revoked.length, 1); assert.deepEqual(f.revoked[0].basis, accepted);
  assert.equal(f.revoked[0].composition, '1'); assert.equal(f.revoked[0].keys.length, 1);
  old.emit('compositionend', {data: 'é'}); await flush(); assert.equal(f.sent.length, 2);
  assert.equal(f.resync.length, 1); assert.equal(f.failures.length, 0);
});

for (const action of ['close', 'publish'])
  test(`known null owner revoke may ${action} without a stale resync or editor resurrection`, async () => {
    let f, acted = false;
    f = fixture({onRevoke() {
      if (acted) return; acted = true;
      if (action === 'close') f.conduit.close();
      else assert.equal(f.publish(basis({value: 'fresh', token: '500', context: '500'})), true);
    }});
    const old = f.conduit.element(); down(old); await flush(); await nullAnswer(f, 0);
    assert.equal(acted, true); assert.equal(f.revoked.length, 1); assert.equal(f.resync.length, 0);
    assert.equal(old.listenerCount(), 0); assert.equal(f.failures.length, 0); assert.equal(f.sent.length, 1);
    assert.equal(f.conduit.state().status, action === 'close' ? 'closed' : 'ready');
    if (action === 'publish') {
      const fresh = f.conduit.element(); assert.notEqual(fresh, old); assert.equal(fresh.value, 'fresh');
      assert.equal(f.root.children.length, 1); assert.equal(f.document.activeElement, fresh);
      assert.equal(f.conduit.state().basis.token, '500');
      down(fresh, 'z', 'KeyZ'); await flush(); assert.equal(f.sent.length, 2);
      assert.equal(f.sent[1].observation.predecessor, null); await f.answer(1);
    } else assert.equal(f.root.children.length, 0);
  });

test('known null external resync may publish the fresh owner after receiving frozen proof', async () => {
  let f, metadata;
  f = fixture({onResync(reason, accepted, value) {
    assert.equal(accepted, null); metadata = value;
    assert.equal(f.conduit.state().basis, null); assert.equal(f.conduit.element(), null);
    assert.equal(f.publish(basis({value: 'fresh', token: '501', context: '501'})), true);
  }});
  const old = f.conduit.element(); down(old); await flush(); await nullAnswer(f, 0);
  assert.equal(metadata.receipt.submittedToken, wide); assert.equal(f.revoked.length, 1);
  assert.equal(f.resync.length, 1); assert.equal(f.conduit.state().basis.token, '501');
  assert.equal(f.conduit.element().value, 'fresh'); assert.equal(f.root.children.length, 1); assert.equal(f.failures.length, 0);
});

test('malformed null retirement fails locally with no owner cleanup or resumable projection', async () => {
  const f = fixture(), old = f.conduit.element(); down(old); await flush(); const head = f.sent[0];
  await nullAnswer(f, 0, {retirement: {availability: 'noneditable', identity: head.basis.identity,
    observationRevision: '0', readbackAttested: true}});
  assert.equal(f.conduit.element(), null); assert.equal(old.listenerCount(), 0); assert.equal(f.root.children.length, 0);
  assert.equal(f.revoked.length, 0); assert.equal(f.resync.length, 0); assert.equal(f.failures.length, 1);
  assert.deepEqual(f.conduit.state().unresolved, head); assert.equal(f.publish(basis({token: '999'})), false);
});

test('late valid null retirement leaves a fresh conduit incarnation intact', async () => {
  const f = fixture(), old = f.conduit.element(); down(old); await flush();
  assert.equal(f.publish(basis({value: 'fresh', token: '502', context: '502'})), true);
  const fresh = f.conduit.element(); down(fresh, 'z', 'KeyZ'); await flush(); assert.equal(f.sent.length, 1);
  await nullAnswer(f, 0); assert.equal(f.sent.length, 2); assert.equal(f.conduit.element(), fresh);
  assert.equal(f.document.activeElement, fresh); assert.equal(fresh.value, 'fresh');
  assert.equal(f.revoked.length, 1); assert.equal(f.resync.length, 0); assert.equal(f.failures.length, 0);
  await f.answer(1); assert.equal(f.conduit.state().basis.identity.context, '502');
});

for (const fault of ['onRevoke', 'onResync'])
  test(`known null ${fault} failure retains the exact checked head during conduit closure`, async () => {
    const f = fixture({[fault]() { throw Error(`retirement ${fault} failed`); }});
    const old = f.conduit.element(); down(old); passage(old, 'a'); await flush(); const head = f.sent[0];
    await nullAnswer(f, 0);
    assert.equal(f.failures.length, 1); assert.match(f.failures[0].message, /retirement .* failed/);
    assert.equal(f.conduit.state().status, 'closed'); assert.equal(f.conduit.state().unresolved, head);
    assert.equal(f.conduit.element(), null); assert.equal(old.listenerCount(), 0); assert.equal(f.root.children.length, 0);
    assert.equal(f.revoked.length, 1); assert.equal(f.resync.length, fault === 'onRevoke' ? 0 : 1);
    assert.equal(f.publish(basis({token: '999'})), false); down(old); passage(old, 'z'); await flush();
    assert.equal(f.sent.length, 1);
  });

test('applied authority-retired available reply settles after local service retirement without a second revoke', async () => {
  let metadata;
  const f = fixture({onResync(reason, accepted, value) { if (accepted === null) metadata = value; }});
  const old = f.conduit.element(); down(old); passage(old, 'a'); await flush(); const head = f.sent[0];
  f.conduit.retire('service retired local editor');
  assert.equal(f.conduit.element(), null); assert.equal(f.revoked.length, 1); assert.equal(old.listenerCount(), 0);
  await nullAnswer(f, 0, {outcome: 'applied', retirement: {availability: 'available', authorityRetired: true,
    identity: structuredClone(head.basis.identity), observationRevision: '1', readbackAttested: true}});
  assert.equal(f.conduit.state().status, 'suspended'); assert.equal(f.conduit.state().basis, null);
  assert.equal(f.conduit.state().unresolved, head); assert.equal(f.conduit.state().pending, 0);
  assert.equal(f.revoked.length, 1); assert.equal(f.resync.length, 2); assert.equal(f.failures.length, 0);
  assert.equal(metadata.receipt.outcome, 'applied'); assert.equal(metadata.receipt.retirement.authorityRetired, true);
  assert.equal(f.root.children.length, 0); down(old); passage(old, 'z'); await flush(); assert.equal(f.sent.length, 1);
  assert.equal(f.publish(basis({value: 'fresh', token: '600', context: '600'})), true);
  down(f.conduit.element(), 'z', 'KeyZ'); await flush(); assert.equal(f.sent[1].observation.predecessor, null);
  await f.answer(1); assert.equal(f.conduit.state().basis.identity.context, '600');
});

for (const authorityRetired of [undefined, false])
  test(`available null reply cannot infer retired authority from ${String(authorityRetired)}`, async () => {
    const f = fixture(), old = f.conduit.element(); down(old); await flush(); const head = f.sent[0];
    f.conduit.retire('local retirement');
    const proof = {availability: 'available', identity: structuredClone(head.basis.identity),
      observationRevision: '1', readbackAttested: true};
    if (authorityRetired !== undefined) proof.authorityRetired = authorityRetired;
    await nullAnswer(f, 0, {outcome: 'applied', retirement: proof});
    assert.equal(f.failures.length, 1); assert.equal(f.conduit.state().unresolved, head);
    assert.equal(f.revoked.length, 1); assert.equal(f.resync.length, 1); assert.equal(f.conduit.element(), null);
  });

// v7: a private-publication gap keeps the cached conduit inert and resumable.
test('pause retains its exact node, queue and session while cancelling fresh ingress', async () => {
  const f = fixture(), node = f.conduit.element(), original = f.actual;
  down(node); passage(node, 'a'); const session = f.conduit.state().session;
  assert.equal(f.conduit.pause(), true); assert.equal(f.conduit.pause(), true);
  assert.equal(f.conduit.state().paused, true); assert.equal(f.conduit.element(), node);
  const blockedKey = down(node, 'z', 'KeyZ'), blockedText = passage(node, 'z');
  assert.equal(blockedKey.defaultPrevented, true); assert.equal(blockedKey.stopped, true);
  assert.equal(blockedText.defaultPrevented, true); assert.equal(node.value, 'a'); await flush();
  assert.equal(f.sent.length, 0); assert.equal(f.revoked.length, 0); assert.equal(f.resync.length, 0);
  assert.equal(f.publish(original), false); assert.equal(f.conduit.state().paused, true);
  assert.equal(f.conduit.resume(original), true); await flush();
  assert.equal(f.conduit.element(), node); assert.equal(f.conduit.state().session, session); assert.equal(f.sent.length, 1);
  await f.answer(0); assert.equal(f.sent.length, 2); await f.answer(1);
  assert.equal(f.sent.length, 2); healthy(f);
});

test('a checked owner prefix may update the paused DOM snapshot without resuming admission', async () => {
  const f = fixture({initial: basis({value: 'abc'})}), node = f.conduit.element();
  down(node, 'ArrowLeft', 'ArrowLeft'); await flush(); f.conduit.pause();
  await f.answer(0, {basis: basis({value: 'abc', first: 2, token: '700', revision: '700'})});
  assert.equal(f.conduit.state().paused, true); assert.equal(node.selectionStart, 2);
  f.document.flushSelection(); assert.equal(f.resync.length, 0); assert.equal(f.sent.length, 1);
  assert.equal(f.conduit.resume(f.actual, {caret: [8, 9, 1, 15]}), true);
  assert.equal(f.conduit.element(), node); assert.equal(node.style.left, '18px'); assert.equal(node.style.top, '29px');
  assert.equal(f.revoked.length, 0); healthy(f);
});

test('pause preserves the local IME transaction through a pending checked receipt', async () => {
  const f = fixture(), node = f.conduit.element(); node.emit('compositionstart'); await flush();
  const session = f.conduit.state().session; f.conduit.pause();
  await f.answer(0, {basis: basis({token: '701'}), composition: {transaction: '1', state: 'pending'}});
  assert.equal(f.conduit.state().paused, true); assert.equal(f.conduit.element(), node);
  assert.equal(f.conduit.resume(f.actual), true); preedit(node, 'é', 'é', 1, 'update-first'); await flush();
  assert.equal(f.sent[1].observation.transaction, '1'); assert.equal(f.sent[1].observation.data.operation, 'update');
  await f.answer(1); assert.equal(f.conduit.state().session, session); assert.equal(f.revoked.length, 0); healthy(f);
});

for (const event of ['owned-keyup', 'compositionupdate', 'changed-input', 'changed-selection', 'uncancelable-beforeinput'])
  test(`paused ${event} resynchronizes its actual local ambiguity without exporting it`, async () => {
    const f = fixture(), node = f.conduit.element(); down(node); await flush(); f.conduit.pause();
    if (event === 'owned-keyup') up(node);
    else if (event === 'compositionupdate') node.emit('compositionupdate', {data: '', cancelable: false});
    else if (event === 'uncancelable-beforeinput') node.emit('beforeinput', {inputType: 'insertText', data: 'z', cancelable: false});
    else {
      if (event === 'changed-input') node.value = 'z'; else { node.value = 'ab'; node.setSelectionRange(0, 0); }
      node.emit(event === 'changed-input' ? 'input' : 'selectionchange', {inputType: 'insertText', data: 'z', cancelable: false});
    }
    assert.equal(f.conduit.state().status, 'suspended'); assert.equal(f.conduit.state().paused, false);
    assert.equal(f.conduit.element(), null); assert.equal(f.revoked.length, 1); assert.equal(f.resync.length, 1);
    assert.match(f.resync[0].reason, /paused.*(changed|ambiguous|unblockable)/i);
    await flush(); assert.equal(f.sent.length, 1); assert.equal(f.failures.length, 0);
  });

test('resume detects an unreported local mutation instead of silently restamping it', () => {
  const f = fixture(), node = f.conduit.element(); f.conduit.pause(); node.value = 'unobserved';
  assert.equal(f.conduit.resume(f.actual), false); assert.equal(f.conduit.state().status, 'suspended');
  assert.equal(f.revoked.length, 1); assert.match(f.resync[0].reason, /paused.*changed/i);
});

test('changed native resume facts require actual resynchronization and a fresh publication', () => {
  const f = fixture(); f.conduit.pause();
  assert.equal(f.conduit.resume(basis({token: '702'})), false);
  assert.equal(f.conduit.state().status, 'suspended'); assert.equal(f.conduit.element(), null);
  assert.equal(f.revoked.length, 1); assert.equal(f.resync.length, 1);
  assert.equal(f.publish(basis({token: '703'})), true); assert.equal(f.conduit.state().paused, false);
});

test('an actual ended null receipt retires paused preedit and preserves the exact native fact', async () => {
  let metadata;
  const f = fixture({onResync(reason, accepted, value) { if (accepted === null) metadata = value; }});
  const node = f.conduit.element(); node.emit('compositionstart'); await flush(); f.conduit.pause();
  const ended = {transaction: '1', state: 'ended'}; await nullAnswer(f, 0, {outcome: 'applied', composition: ended});
  assert.equal(f.conduit.state().basis, null); assert.equal(f.conduit.state().paused, false);
  assert.equal(f.conduit.element(), null); assert.equal(f.revoked.length, 1); assert.equal(f.sent.length, 1);
  assert.deepEqual(metadata.receipt.composition, ended); assert.equal(metadata.receipt.outcome, 'applied');
  assert.equal(f.revoked[0].composition, '1'); assert.equal(f.failures.length, 0);
});

test('unknown outcome while paused remains local-only terminal teardown with its original head', async () => {
  const f = fixture(), node = f.conduit.element(); down(node); await flush(); const head = f.sent[0];
  f.conduit.pause(); await f.answer(0, {outcome: 'unknown'});
  assert.equal(f.conduit.element(), null); assert.equal(f.revoked.length, 0); assert.equal(f.resync.length, 0);
  assert.equal(f.conduit.state().unresolved, head); assert.equal(f.conduit.state().paused, false);
  assert.equal(f.failures.length, 1); assert.equal(f.conduit.resume(head.basis), false);
});

test('pause before any owned controller publication remains detached and inert', () => {
  const f = fixture({publish: false}); assert.equal(f.conduit.pause(), false);
  assert.equal(f.conduit.state().status, 'detached'); assert.equal(f.conduit.state().paused, false);
  assert.equal(f.conduit.element(), null); assert.equal(f.sent.length, 0); healthy(f);
});

for (const phase of ['onAppend', 'onRevoke'])
  test(`${phase} can pause an initializing publication without focus or admission authority`, async () => {
    let f, armed = false, paused;
    f = fixture({publish: false, [phase]() { if (armed) paused = f.conduit.pause(); }});
    if (phase === 'onRevoke') assert.equal(f.publish(), true);
    armed = true;
    const next = basis({value: 'pending', token: '800', context: '800'});
    assert.equal(f.publish(next), false); assert.equal(paused, true);
    const node = f.conduit.element(), session = f.conduit.state().session;
    assert.equal(f.conduit.state().paused, true); assert.equal(node.value, 'pending');
    assert.equal(f.document.activeElement, null); assert.equal(f.root.children.length, 1);
    await flush(); assert.equal(f.sent.length, 0); assert.equal(f.resync.length, 0);
    assert.equal(f.revoked.length, phase === 'onRevoke' ? 1 : 0);
    // A fresh exact owner publication authorizes resume; the pending marker did
    // not create focus. The original browser focus is still unchanged here.
    assert.equal(f.conduit.resume(f.conduit.state().basis, {focused: true}), true);
    assert.equal(f.document.activeElement, node); assert.equal(f.conduit.state().session, session);
    assert.equal(f.conduit.state().paused, false); assert.equal(f.conduit.element(), node);
    down(node, 'z', 'KeyZ'); await flush(); assert.equal(f.sent.length, 1);
    await f.answer(0, {basis: basis({value: 'pending', token: '801', context: '800'})});
    assert.equal(f.failures.length, 0); assert.equal(f.resync.length, 0);
  });

test('initial paused resume cannot replace browser focus acquired by a foreign element', () => {
  let f;
  f = fixture({publish: false, onAppend() { assert.equal(f.conduit.pause(), true); }});
  assert.equal(f.publish(basis({value: 'pending', token: '802'})), false);
  const foreign = {}; f.document.activeElement = foreign;
  assert.equal(f.conduit.resume(f.conduit.state().basis), false);
  assert.equal(f.document.activeElement, foreign); assert.equal(f.conduit.element(), null);
  assert.equal(f.conduit.state().status, 'suspended'); assert.equal(f.revoked.length, 1);
  assert.match(f.resync[0].reason, /eligibility changed/); assert.equal(f.sent.length, 0); assert.equal(f.failures.length, 0);
});
