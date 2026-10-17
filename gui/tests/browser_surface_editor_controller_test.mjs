// SPDX-License-Identifier: CC0-1.0
// Owned observation/receipt model only; no DOM, browser, IME or engine proof.
import assert from 'node:assert/strict';
import test from 'node:test';
import {pathToFileURL} from 'node:url';

const {copyEditorBasis, copyEditorRetirement, createEditorObservationController} = await import(process.argv[2]
  ? pathToFileURL(process.argv[2]) : new URL('../host/browser_surface_editor_controller.mjs', import.meta.url));
const clone = value => structuredClone(value);
const encoder = new TextEncoder();
const wide = '9007199254740993', maximum = '18446744073709551615';
const flush = () => new Promise(resolve => setImmediate(resolve));
const native = (value = 'abc', first = value.length, last = first, direction = 'none') =>
  ({value, selectionStart: first, selectionEnd: last, selectionDirection: direction});
const basis = ({token = '1', revision = wide, value = 'abc', first = value.length, last = first,
  backward = false, composition = '0', context = '7', identity = {}} = {}) => ({
  token, editorRevision: revision, surrounding: value,
  selection: [encoder.encode(value.slice(0, first)).length, encoder.encode(value.slice(0, last)).length],
  backward, composition, identity: {owner: {id: 'editor', generation: wide}, presentationRevision: wide,
    generation: '5', epoch: '6', context, ...identity}
});
const observation = ({kind = 'text', authority = 'range', group = null, groupEnd = false,
  transaction = '0', before = native(), after = native('abcX'),
  data = {inputType: 'insertText', text: 'X'}} = {}) =>
  ({kind, authority, group, groupEnd, transaction, before, after, data});
const key = ({group = wide, before = native(), phase = 'down'} = {}) => observation({
  kind: 'key', authority: 'native', group, before, after: null,
  data: {phase, key: 'a', code: 'KeyA', location: 0, modifiers: 0, repeat: false}
});
const ime = (operation, before, after, transaction = wide) => observation({
  kind: 'composition', authority: operation === 'begin' ? 'range' : 'composition',
  transaction, before, after, data: {operation, text: operation === 'begin' ? '' : 'é'}
});
const receipt = (packet, next = packet.basis, changes = {}) => ({
  session: packet.session, id: packet.observation.id, predecessor: packet.observation.predecessor,
  submittedToken: packet.basis.token, outcome: 'applied', basis: next, continuity: 'same',
  defaultToken: null, composition: null, ...changes
});
function fixture(options = {}) {
  const sent = [], pending = [], accepted = [], resync = [], failures = [];
  const controller = createEditorObservationController({
    send(packet) {
      sent.push(packet);
      if (options.send) return options.send(packet);
      return new Promise((resolve, reject) => pending.push({resolve, reject}));
    },
    onBasis(value, metadata) { accepted.push({value, metadata}); options.onBasis?.(value, metadata); },
    onResync(reason, value, metadata) { resync.push({reason, value}); options.onResync?.(reason, value, metadata); },
    onFailure(error) { failures.push(error); options.onFailure?.(error); },
    ...(options.maxPending === undefined ? {} : {maxPending: options.maxPending}),
    ...(options.maxBytes === undefined ? {} : {maxBytes: options.maxBytes})
  });
  if (options.activate !== false) assert.equal(controller.activate(options.initial ?? basis()), options.activationResult ?? true);
  return {controller, sent, pending, accepted, resync, failures,
    resolve(index, next, changes) { const value = receipt(sent[index], next, changes); pending[index].resolve(value); return value; }};
}
function terminal(f, expectedSends = f.sent.length) {
  assert.equal(f.controller.state().status, 'terminal_unknown');
  assert.equal(f.controller.activate(basis({token: '99'})), false);
  assert.equal(f.controller.observe(observation()), null);
  assert.equal(f.sent.length, expectedSends);
  assert.equal(f.failures.length, 1);
}

test('activation owns full-width basis, byte ranges and recursively frozen state', () => {
  const input = basis({token: maximum, revision: maximum, value: 'aé😀z', first: 1, last: 4, backward: true,
    identity: {owner: {id: 'editor', generation: maximum}, presentationRevision: maximum,
      generation: maximum, epoch: maximum, context: maximum}});
  const copied = copyEditorBasis(input), f = fixture({initial: input});
  input.identity.owner.id = 'reused'; input.selection[0] = 0; input.surrounding = 'changed';
  assert.deepEqual(copied.selection, [1, 7]);
  assert.equal(copied.identity.context, maximum); assert.equal(copied.editorRevision, maximum);
  assert.equal(f.controller.state().basis.identity.owner.id, 'editor');
  assert.equal(f.controller.state().basis.surrounding, 'aé😀z');
  for (const value of [f.controller, f.controller.state(), copied, copied.selection, copied.identity, copied.identity.owner])
    assert.equal(Object.isFrozen(value), true);
  assert.throws(() => { copied.selection[0] = 0; }, TypeError);
});

test('invalid basis identifiers and non-scalar byte selections reject before activation', () => {
  for (const invalid of ['0', '-1', '01', '18446744073709551616', 1, 9007199254740992]) {
    const input = basis(); input.token = invalid; assert.throws(() => copyEditorBasis(input));
  }
  for (const change of [value => { value.editorRevision = '0'; }, value => { value.composition = '01'; },
    value => { value.identity.context = '0'; }, value => { value.identity.owner.id = ''; },
    value => { value.selection = [1, 1]; value.surrounding = 'é'; },
    value => { value.selection = [1, 1]; value.surrounding = '😀'; }, value => { value.backward = 0; }]) {
    const input = basis(); change(input); assert.throws(() => copyEditorBasis(input));
  }
});

test('basis getters never execute while rejection leaves detached state intact', () => {
  let reads = 0;
  const input = basis(); Object.defineProperty(input.identity, 'context', {enumerable: true, get() { ++reads; return '7'; }});
  const f = fixture({activate: false});
  assert.throws(() => f.controller.activate(input)); assert.equal(reads, 0);
  assert.equal(f.controller.state().status, 'detached'); assert.equal(f.controller.observe(observation()), null);
  assert.equal(f.sent.length, 0);
});

test('a native burst exports one flight with checked predecessors and actual arbitrary revisions', async () => {
  const f = fixture();
  assert.equal(f.controller.observe(observation()), '1');
  assert.equal(f.controller.observe(observation({before: native('abcX'), after: native('abcXY'), data: {text: 'Y'}})), '2');
  assert.equal(f.controller.observe(observation({kind: 'selection', before: native('abcXY'),
    after: native('abcXY', 1, 3, 'backward'), data: {selection: true}})), '3');
  await flush(); assert.equal(f.sent.length, 1); assert.equal(f.controller.state().pending, 3);
  assert.equal(f.sent[0].observation.predecessor, null);
  f.resolve(0, basis({token: '12', revision: '8128', value: 'abcX'})); await flush();
  assert.equal(f.sent.length, 2); assert.equal(f.sent[1].basis.editorRevision, '8128');
  assert.equal(f.sent[1].basis.token, '12'); assert.equal(f.sent[1].observation.predecessor, '1');
  f.resolve(1, basis({token: '13', revision: '3', value: 'abcXY'})); await flush();
  assert.equal(f.sent[2].observation.predecessor, '2'); assert.equal(f.sent[2].basis.editorRevision, '3');
  f.resolve(2, basis({token: '14', revision: maximum, value: 'abcXY', first: 1, last: 3, backward: true})); await flush();
  assert.equal(f.controller.state().pending, 0); assert.equal(f.controller.state().bytes, 0);
  assert.equal(f.controller.state().basis.editorRevision, maximum); assert.equal(f.failures.length, 0);
  assert.deepEqual(f.accepted.slice(1).map(value => value.metadata.preservePassage), [true, true, false]);
});

test('observations and nested data remain owned after caller mutation', async () => {
  const f = fixture(), input = observation({data: {text: 'X', copied: [{value: wide}]}});
  f.controller.observe(input); input.before.value = 'foreign'; input.data.text = 'changed'; input.data.copied[0].value = '0';
  await flush(); const packet = f.sent[0];
  assert.equal(packet.observation.before.value, 'abc'); assert.equal(packet.observation.data.text, 'X');
  assert.equal(packet.observation.data.copied[0].value, wide);
  for (const item of [packet, packet.basis, packet.observation, packet.observation.before,
    packet.observation.before.selection, packet.observation.data.copied[0]]) assert.equal(Object.isFrozen(item), true);
  assert.throws(() => { packet.basis.token = '2'; }, TypeError);
  const next = basis({token: '2', value: 'abcX'}), raw = f.resolve(0, next); await flush();
  next.surrounding = 'reused'; raw.basis.selection[0] = 0;
  assert.equal(f.controller.state().basis.surrounding, 'abcX');
  assert.deepEqual(f.controller.state().basis.selection, [4, 4]);
});

test('identical activate preserves an awaiting incarnation and queued observations', async () => {
  const initial = basis(), f = fixture({initial}); f.controller.observe(observation()); await flush();
  const before = f.controller.state(); assert.equal(f.controller.activate(clone(initial)), true);
  assert.equal(f.controller.state().session, before.session); assert.equal(f.controller.state().status, 'awaiting');
  assert.equal(f.sent.length, 1); f.resolve(0, basis({token: '2', value: 'abcX'})); await flush();
  assert.equal(f.controller.state().status, 'ready'); assert.equal(f.sent.length, 1);
});

for (const field of ['session', 'id', 'predecessor', 'submittedToken']) test(`mismatched receipt ${field} is terminal without exporting its tail`, async () => {
  const f = fixture(); f.controller.observe(observation()); f.controller.observe(key()); await flush();
  f.resolve(0, basis({token: '2', value: 'abcX'}), {[field]: '999'}); await flush();
  terminal(f, 1); assert.equal(f.controller.state().unresolved, f.sent[0]);
});

test('receipt getters reject without execution and cannot publish a basis', async () => {
  const f = fixture(); f.controller.observe(observation()); await flush(); let reads = 0;
  const raw = receipt(f.sent[0], basis({token: '2', value: 'abcX'}));
  Object.defineProperty(raw, 'outcome', {enumerable: true, get() { ++reads; return 'applied'; }});
  f.pending[0].resolve(raw); await flush(); terminal(f, 1);
  assert.equal(reads, 0); assert.equal(f.accepted.length, 1);
});

test('a changed predecessor projection retires range-dependent tail without restamping it', async () => {
  const f = fixture(); f.controller.observe(observation());
  f.controller.observe(observation({before: native('abcX'), after: native('abcXY')})); await flush();
  f.resolve(0, basis({token: '2', revision: '700', value: 'script', first: 0})); await flush();
  assert.equal(f.sent.length, 1); assert.equal(f.controller.state().status, 'suspended');
  assert.equal(f.controller.state().basis.editorRevision, '700'); assert.equal(f.failures.length, 0);
  assert.match(f.resync.at(-1).reason, /projection/i);
});

test('range selection and direction are part of predecessor projection', async () => {
  const f = fixture({initial: basis({first: 1, last: 2, backward: true})});
  f.controller.observe(observation({kind: 'selection', before: native('abc', 1, 2, 'forward'), after: native('abc', 0), data: {}}));
  await flush(); assert.equal(f.sent.length, 0); assert.equal(f.controller.state().status, 'suspended');
});

test('same continuity cannot silently change context', async () => {
  const f = fixture(); f.controller.observe(key()); f.controller.observe(key()); await flush();
  f.resolve(0, basis({token: '2', context: '99'})); await flush(); terminal(f, 1);
});

test('a key retarget continues native keys but invalidates old range authority', async () => {
  const f = fixture(); f.controller.observe(key()); f.controller.observe(key({group: '42'})); await flush();
  f.resolve(0, basis({token: '2', context: '99', revision: '21'}), {continuity: 'key-retarget'}); await flush();
  assert.equal(f.sent[1].basis.identity.context, '99'); assert.equal(f.sent[1].basis.editorRevision, '21');
  f.resolve(1, basis({token: '3', context: '99'})); await flush();
  const range = fixture(); range.controller.observe(key()); range.controller.observe(observation()); await flush();
  range.resolve(0, basis({token: '2', context: '99'}), {continuity: 'key-retarget'}); await flush();
  assert.equal(range.sent.length, 1); assert.equal(range.controller.state().status, 'suspended');
});

test('a range receipt cannot claim key-retarget authority', async () => {
  const f = fixture(); f.controller.observe(observation()); await flush();
  f.resolve(0, basis({token: '2', context: '99', value: 'abcX'}), {continuity: 'key-retarget'}); await flush(); terminal(f, 1);
});

for (const outcome of ['cancelled', 'rejected']) test(`${outcome} receipt publishes known basis and discards its tail`, async () => {
  const f = fixture(); f.controller.observe(key()); f.controller.observe(observation()); await flush();
  const next = basis({token: '2', revision: '8192'}); f.resolve(0, next, {outcome}); await flush();
  assert.equal(f.controller.state().status, 'suspended'); assert.equal(f.sent.length, 1);
  assert.equal(f.controller.observe(observation()), null); assert.equal(f.failures.length, 0);
  assert.equal(f.controller.state().basis.token, '2'); assert.equal(f.accepted.at(-1).metadata.preservePassage, false);
  assert.match(f.resync.at(-1).reason, new RegExp(outcome));
});

test('replaced receipt retires remaining chain and resynchronizes to actual replacement', async () => {
  const f = fixture(); f.controller.observe(key()); f.controller.observe(observation()); await flush();
  f.resolve(0, basis({token: '2', context: '88'}), {continuity: 'replaced'}); await flush();
  assert.equal(f.controller.state().status, 'suspended'); assert.equal(f.controller.state().basis.identity.context, '88');
  assert.equal(f.sent.length, 1); assert.equal(f.failures.length, 0);
});

test('unknown receipt keeps original unresolved authority and permanently stops exports', async () => {
  const f = fixture(); f.controller.observe(key()); f.controller.observe(observation()); await flush();
  f.resolve(0, undefined, {outcome: 'unknown'}); await flush(); terminal(f, 1);
  assert.equal(f.controller.state().unresolved, f.sent[0]); assert.equal(f.accepted.length, 1);
});

test('synchronous send throw and rejected transport promise are terminal once', async () => {
  const thrown = fixture({send() { throw Error('send failed'); }}); thrown.controller.observe(key()); await flush(); terminal(thrown, 1);
  const rejected = fixture(); rejected.controller.observe(key()); await flush(); rejected.pending[0].reject(Error('unknown delivery'));
  await flush(); terminal(rejected, 1);
});

test('new incarnation waits for old known receipt and never reinstalls old basis', async () => {
  const f = fixture(); f.controller.observe(key()); await flush(); const first = f.sent[0];
  assert.equal(f.controller.activate(basis({token: '9', context: '99'})), true);
  f.controller.observe(key()); await flush(); assert.equal(f.sent.length, 1, 'one outstanding owner call across replacement');
  f.resolve(0, basis({token: '2'})); await flush();
  assert.equal(f.sent.length, 2); assert.notEqual(f.sent[1].session, first.session);
  assert.equal(f.sent[1].basis.token, '9'); assert.equal(f.sent[1].observation.predecessor, null);
  assert.equal(f.accepted.at(-1).value.token, '9');
  f.resolve(1, basis({token: '10', context: '99'})); await flush(); assert.equal(f.controller.state().basis.token, '10');
});

test('unknown old outstanding result still blocks the replacement incarnation', async () => {
  const f = fixture(); f.controller.observe(key()); await flush();
  f.controller.activate(basis({token: '9', context: '99'})); f.controller.observe(key());
  f.resolve(0, undefined, {outcome: 'unknown'}); await flush(); terminal(f, 1);
  assert.equal(f.controller.state().unresolved, f.sent[0]);
});

test('retire and close discard queued observations and ignore late known publication', async () => {
  for (const close of [false, true]) {
    const f = fixture(); f.controller.observe(key()); f.controller.observe(observation()); await flush();
    if (close) { f.controller.close(); f.controller.close(); } else f.controller.retire('service replaced');
    assert.equal(f.controller.observe(key()), null); assert.equal(f.controller.state().unresolved, f.sent[0]);
    f.resolve(0, basis({token: '2'})); await flush(); assert.equal(f.sent.length, 1); assert.equal(f.accepted.length, 1);
    assert.equal(f.controller.state().status, close ? 'closed' : 'suspended'); assert.equal(f.failures.length, 0);
    if (close) assert.equal(f.controller.activate(basis()), false);
    else assert.match(f.resync.at(-1).reason, /service replaced/);
  }
});

test('a queued keyboard default receives no export without an owner token', async () => {
  const f = fixture(); f.controller.observe(key());
  f.controller.observe(observation({authority: 'default', group: wide, groupEnd: true})); await flush();
  f.resolve(0, basis({token: '2'})); await flush();
  assert.equal(f.sent.length, 1); assert.equal(f.controller.state().status, 'suspended');
  assert.match(f.resync.at(-1).reason, /not authorized/i); assert.equal(f.failures.length, 0);
});

test('owner default group uses actual post-key mapping and retires its token at group end', async () => {
  const f = fixture(); f.controller.observe(key());
  f.controller.observe(observation({authority: 'default', group: wide, before: native(), after: native('abcX')}));
  f.controller.observe(observation({authority: 'default', group: wide, groupEnd: true,
    before: native('abcX'), after: native('abcXY'), data: {text: 'Y'}})); await flush();
  f.resolve(0, basis({token: '2', first: 0, revision: '4096'}), {defaultToken: {group: wide, token: maximum}}); await flush();
  assert.equal(f.sent[1].basis.editorRevision, '4096'); assert.deepEqual(f.sent[1].basis.selection, [0, 0]);
  assert.deepEqual(f.sent[1].observation.before.selection, [3, 3]); assert.equal(f.sent[1].defaultToken, maximum);
  f.resolve(1, basis({token: '3', value: 'Xabc', first: 1})); await flush(); assert.equal(f.sent[2].defaultToken, maximum);
  f.resolve(2, basis({token: '4', value: 'XYabc', first: 2})); await flush();
  f.controller.observe(observation({authority: 'default', group: wide, groupEnd: true,
    before: native('XYabc', 2), after: native('XYZabc', 3)})); await flush();
  assert.equal(f.sent.length, 3); assert.equal(f.controller.state().status, 'suspended');
});

test('owner default token must join exact source group and keydown phase', async () => {
  for (const [input, token] of [[key(), {group: '42', token: '5'}],
    [key({phase: 'up'}), {group: wide, token: '5'}], [observation(), {group: wide, token: '5'}]]) {
    const f = fixture(); f.controller.observe(input); await flush(); f.resolve(0, basis({token: '2'}), {defaultToken: token});
    await flush(); terminal(f, 1);
  }
});

test('native incarnation replacement revokes an otherwise live keyboard default token', async () => {
  const f = fixture(); f.controller.observe(key()); await flush();
  f.resolve(0, basis({token: '2'}), {defaultToken: {group: wide, token: maximum}}); await flush();
  f.controller.activate(basis({token: '9', context: '99'}));
  f.controller.observe(observation({authority: 'default', group: wide, groupEnd: true})); await flush();
  assert.equal(f.sent.length, 1); assert.equal(f.controller.state().status, 'suspended');
  assert.match(f.resync.at(-1).reason, /not authorized/i); assert.equal(f.failures.length, 0);
});

test('independently opened default groups are bounded even after their key calls settle', async () => {
  const f = fixture({maxPending: 2});
  for (let index = 0; index < 3; ++index) {
    const group = String(index + 10); f.controller.observe(key({group})); await flush();
    f.resolve(index, basis({token: String(index + 2)}), {defaultToken: {group, token: String(index + 20)}}); await flush();
  }
  assert.equal(f.sent.length, 3); assert.equal(f.controller.state().status, 'suspended');
  assert.match(f.resync.at(-1).reason, /group limit/i); assert.equal(f.failures.length, 0);
  assert.equal(f.controller.observe(key({group: '99'})), null);
});

test('an explicitly closed key group cannot grant a later default passage', async () => {
  const f = fixture(), closed = key(); closed.groupEnd = true; f.controller.observe(closed);
  f.controller.observe(observation({authority: 'default', group: wide, groupEnd: true})); await flush();
  f.resolve(0, basis({token: '2'}), {defaultToken: {group: wide, token: maximum}}); await flush();
  assert.equal(f.sent.length, 1); assert.equal(f.controller.state().status, 'suspended');
  assert.match(f.resync.at(-1).reason, /not authorized/i);
});

test('IME begin, update and commit queue before first receipt and use actual attestations', async () => {
  const initial = basis({first: 1}), f = fixture({initial});
  f.controller.observe(ime('begin', native('abc', 1), native('abc', 1)));
  f.controller.observe(ime('update', native('abc', 1), native('aébc', 2)));
  f.controller.observe(ime('commit', native('aébc', 2), native('aébc', 2))); await flush();
  f.resolve(0, basis({token: '2', first: 1, revision: '51'}), {composition: {transaction: wide, state: 'pending'}}); await flush();
  assert.equal(f.sent[1].observation.transaction, wide); assert.equal(f.sent[1].basis.editorRevision, '51');
  f.resolve(1, basis({token: '3', value: 'aébc', first: 2, revision: '8191', composition: wide}),
    {composition: {transaction: wide, state: 'live'}}); await flush();
  assert.equal(f.sent[2].basis.composition, wide); assert.deepEqual(f.sent[2].basis.selection, [3, 3]);
  f.resolve(2, basis({token: '4', value: 'aébc', first: 2, revision: '9'}),
    {composition: {transaction: wide, state: 'ended'}}); await flush();
  assert.equal(f.controller.state().status, 'ready'); assert.equal(f.controller.state().pending, 0);
  assert.deepEqual(f.accepted.slice(1).map(value => value.metadata.preservePassage), [true, true, false]);
  assert.equal(f.controller.state().basis.composition, '0'); assert.equal(f.failures.length, 0);
});

test('IME continuation cannot export under a different transaction', async () => {
  const f = fixture({initial: basis({first: 1})});
  f.controller.observe(ime('begin', native('abc', 1), native('abc', 1)));
  await flush(); // The invalid successor must not discard an as-yet unsent prefix.
  f.controller.observe(ime('update', native('abc', 1), native('aébc', 2), '42')); await flush();
  f.resolve(0, basis({token: '2', first: 1}), {composition: {transaction: wide, state: 'pending'}}); await flush();
  assert.equal(f.sent.length, 1); assert.equal(f.controller.state().status, 'suspended');
  assert.match(f.resync.at(-1).reason, /composition (?:predecessor|ordering)/i);
});

for (const fault of ['missing', 'transaction', 'live', 'ended']) test(`invalid IME ${fault} attestation is terminal`, async () => {
  const f = fixture({initial: basis({first: 1})});
  const ending = fault === 'ended';
  f.controller.observe(ime('begin', native('abc', 1), native('abc', 1))); await flush();
  if (ending) {
    f.resolve(0, basis({token: '2', first: 1, composition: wide}), {composition: {transaction: wide, state: 'live'}}); await flush();
    f.controller.observe(ime('commit', native('abc', 1), native('abc', 1))); await flush();
    f.resolve(1, basis({token: '3', first: 1, composition: wide}), {composition: {transaction: wide, state: 'ended'}});
  } else {
    const composition = fault === 'missing' ? null : {transaction: fault === 'transaction' ? '42' : wide, state: 'live'};
    f.resolve(0, basis({token: '2', first: 1}), {composition});
  }
  await flush(); terminal(f, ending ? 2 : 1);
});

test('non-composition receipt cannot silently lose a live native composition', async () => {
  const f = fixture({initial: basis({first: 1})});
  f.controller.observe(ime('begin', native('abc', 1), native('abc', 1))); await flush();
  f.resolve(0, basis({token: '2', first: 1, composition: wide}), {composition: {transaction: wide, state: 'live'}}); await flush();
  f.controller.observe(key({before: native('abc', 1)})); await flush();
  f.resolve(1, basis({token: '3', first: 1, composition: wide})); await flush(); terminal(f, 2);
});

test('native key receipts preserve a live composition and its queued successor', async () => {
  const f = fixture({initial: basis({first: 1})});
  f.controller.observe(ime('begin', native('abc', 1), native('abc', 1))); await flush();
  f.resolve(0, basis({token: '2', first: 1, composition: wide}), {composition: {transaction: wide, state: 'live'}}); await flush();
  f.controller.observe(key({before: native('abc', 1)}));
  f.controller.observe(ime('cancel', native('abc', 1), native('abc', 1))); await flush();
  f.resolve(1, basis({token: '3', first: 1, composition: wide}), {composition: {transaction: wide, state: 'live'}}); await flush();
  assert.equal(f.sent.length, 3); assert.equal(f.sent[2].basis.composition, wide);
  f.resolve(2, basis({token: '4', first: 1}), {composition: {transaction: wide, state: 'ended'}}); await flush();
  assert.equal(f.controller.state().status, 'ready'); assert.equal(f.controller.state().basis.composition, '0');
  assert.equal(f.accepted.at(-1).metadata.preservePassage, false); assert.equal(f.failures.length, 0);
});

test('queue capacity includes in-flight work and overflow retires the tail without sending it', async () => {
  const f = fixture({maxPending: 2}); f.controller.observe(key()); await flush();
  assert.equal(f.controller.observe(key()), '2'); assert.equal(f.controller.observe(key()), null);
  assert.equal(f.controller.state().status, 'suspended'); assert.equal(f.sent.length, 1);
  assert.equal(f.controller.state().bytes, 0); assert.equal(f.controller.state().unresolved, f.sent[0]);
  f.resolve(0, basis({token: '2'})); await flush(); assert.equal(f.sent.length, 1);
  f.controller.activate(basis({token: '9'})); assert.equal(f.controller.observe(key()), '3'); await flush();
  assert.equal(f.sent[1].observation.predecessor, null);
});

test('byte budget exhaustion exports no oversized observation', async () => {
  const f = fixture({maxBytes: 32}); assert.equal(f.controller.observe(observation()), null); await flush();
  assert.equal(f.sent.length, 0); assert.equal(f.controller.state().status, 'suspended');
  assert.equal(f.controller.state().bytes, 0); assert.match(f.resync.at(-1).reason, /queue exhausted/i);
});

test('complete packet ownership limit suspends without uncaught microtask or dropped accounting', async () => {
  const f = fixture(), data = Object.fromEntries(Array.from({length: 210}, (_, index) => [`f${index}`, index]));
  f.controller.observe(observation({kind: 'selection', before: native(), after: native(), data})); await flush();
  assert.equal(f.sent.length, 0); assert.equal(f.controller.state().status, 'suspended');
  assert.equal(f.controller.state().pending, 0); assert.equal(f.controller.state().bytes, 0);
  assert.equal(f.failures.length, 0); assert.equal(f.resync.length, 1);
});

test('queue bounds include an old outstanding call after native incarnation replacement', async () => {
  const f = fixture({maxPending: 1}); f.controller.observe(key()); await flush();
  f.controller.activate(basis({token: '9', context: '99'}));
  assert.equal(f.controller.observe(key()), null); assert.equal(f.controller.state().status, 'suspended');
  assert.equal(f.sent.length, 1); f.resolve(0, basis({token: '2'})); await flush();
  assert.equal(f.sent.length, 1); assert.equal(f.controller.state().basis.token, '9');
});

test('constructor limits and callback types reject without work', () => {
  for (const value of [0, -1, 65, 1.5, Infinity]) assert.throws(() => createEditorObservationController({send() {}, maxPending: value}));
  for (const value of [0, -1, 1048577, 1.5, Infinity]) assert.throws(() => createEditorObservationController({send() {}, maxBytes: value}));
  assert.throws(() => createEditorObservationController());
  for (const callback of ['send', 'onBasis', 'onResync', 'onFailure'])
    assert.throws(() => createEditorObservationController({send() {}, [callback]: null}));
});

test('malformed observations suspend without exporting or invoking accessors', async () => {
  let reads = 0;
  const malformed = [value => { value.kind = 'paste'; }, value => { value.authority = 'guessed'; },
    value => { value.transaction = '42'; }, value => { value.authority = 'default'; },
    value => { value.before = native('😀', 1); }, value => { value.data = {text: '\ud800'}; },
    value => { value.data = {text: 'x'.repeat(65537)}; }, value => { value.data = {unsafe: NaN}; },
    value => { value.data = new Date(); }, value => { value.data = {items: Array(2)}; },
    value => { value.data = {items: Array(65).fill(0)}; }, value => { value.data = {}; value.data.loop = value.data; },
    value => { value.kind = 'key'; value.authority = 'range'; value.data = {phase: 'down'}; },
    value => { value.kind = 'key'; value.authority = 'native'; value.data = {phase: 'keypress'}; },
    value => { value.kind = 'selection'; value.authority = 'native'; }, value => { value.authority = 'native'; },
    value => { value.kind = 'composition'; value.transaction = wide; value.data = {operation: 'update'}; },
    value => { Object.defineProperty(value, 'kind', {enumerable: true, get() { ++reads; return 'text'; }}); },
    value => { Object.defineProperty(value.before, 'value', {enumerable: true, get() { ++reads; return 'abc'; }}); },
    value => { Object.defineProperty(value.data, 'text', {enumerable: true, get() { ++reads; return 'X'; }}); }];
  for (const change of malformed) {
    const f = fixture(), input = observation(); change(input); assert.equal(f.controller.observe(input), null); await flush();
    assert.equal(f.sent.length, 0); assert.equal(f.controller.state().status, 'suspended'); assert.equal(f.failures.length, 0);
  }
  assert.equal(reads, 0);
});

test('throwing observer callbacks cannot resume exporting after uncertain publication', async () => {
  const initial = fixture({onBasis() { throw Error('publication failed'); }, activationResult: false}); terminal(initial, 0);
  const f = fixture({onFailure() { throw Error('report failed'); }}); f.controller.observe(key()); await flush();
  f.resolve(0, undefined, {outcome: 'unknown'}); await flush(); terminal(f, 1);
  f.controller.close(); assert.equal(f.controller.state().status, 'closed');
});

// Successor cases: all original45 functions/assertions remain above. The one
// extra flush preserves the old wrong-transaction test's entered-prefix intent.
test('dead-key dependencies preserve all owner tokens through keyup and spend them at passage end', async () => {
  const dead = wide, primary = maximum, dependencies = [dead, primary], f = fixture();
  f.controller.observe(key({group: dead}));
  const up = key({group: dead, phase: 'up'}); up.groupEnd = false; f.controller.observe(up);
  f.controller.observe(key({group: primary}));
  f.controller.observe(observation({authority: 'default', group: primary, data: {text: 'é', sourceGroups: dependencies},
    before: native(), after: native('abcé')}));
  f.controller.observe(observation({authority: 'default', group: primary, groupEnd: true,
    data: {text: '!', sourceGroups: [dead, primary]}, before: native('abcé'), after: native('abcé!')}));
  dependencies[0] = '9'; await flush();
  f.resolve(0, basis({token: '2'}), {defaultToken: {group: dead, token: '31'}}); await flush();
  assert.equal(f.sent[1].observation.kind, 'key'); assert.equal(f.sent[1].observation.data.phase, 'up');
  f.resolve(1, basis({token: '3'})); await flush();
  f.resolve(2, basis({token: '4', first: 0}), {defaultToken: {group: primary, token: '32'}}); await flush();
  const expected = [{group: dead, token: '31'}, {group: primary, token: '32'}];
  assert.deepEqual(f.sent[3].defaultDependencies, expected); assert.equal(f.sent[3].defaultToken, '32');
  assert.deepEqual(f.sent[3].observation.data.sourceGroups, [dead, primary]);
  assert.equal(Object.isFrozen(f.sent[3].defaultDependencies), true);
  assert.equal(Object.isFrozen(f.sent[3].defaultDependencies[0]), true);
  assert.deepEqual(f.sent[3].basis.selection, [0, 0]);
  f.resolve(3, basis({token: '5', value: 'éabc', first: 1})); await flush();
  assert.deepEqual(f.sent[4].defaultDependencies, expected);
  f.resolve(4, basis({token: '6', value: 'é!abc', first: 2})); await flush();
  f.controller.observe(observation({authority: 'default', group: dead, groupEnd: true,
    data: {sourceGroups: [dead]}, before: native('é!abc', 2), after: native('é!abcX', 6)})); await flush();
  assert.equal(f.sent.length, 5); assert.equal(f.controller.state().status, 'suspended');
  assert.match(f.resync.at(-1).reason, /not authorized/i); assert.equal(f.failures.length, 0);
});

test('a later base-key token cannot bypass a missing dead-key token', async () => {
  const dead = '41', primary = '42', f = fixture();
  f.controller.observe(key({group: dead})); f.controller.observe(key({group: dead, phase: 'up'}));
  f.controller.observe(key({group: primary}));
  f.controller.observe(observation({authority: 'default', group: primary, groupEnd: true,
    data: {text: 'é', sourceGroups: [dead, primary]}})); await flush();
  f.resolve(0, basis({token: '2'})); await flush(); // Known key dispatch, no default permission.
  f.resolve(1, basis({token: '3'})); await flush();
  f.resolve(2, basis({token: '4'}), {defaultToken: {group: primary, token: '32'}}); await flush();
  assert.equal(f.sent.length, 3); assert.equal(f.controller.state().status, 'suspended');
  assert.match(f.resync.at(-1).reason, /not authorized/i); assert.equal(f.failures.length, 0);
});

test('cancelled dead-key prefix discards the dependent base key and text without export', async () => {
  const f = fixture(); f.controller.observe(key({group: '41'})); f.controller.observe(key({group: '42'}));
  f.controller.observe(observation({authority: 'default', group: '42', groupEnd: true,
    data: {sourceGroups: ['41', '42']}})); await flush();
  f.resolve(0, basis({token: '2'}), {outcome: 'cancelled'}); await flush();
  assert.equal(f.sent.length, 1); assert.equal(f.controller.state().status, 'suspended');
  assert.equal(f.controller.observe(key()), null); assert.equal(f.failures.length, 0);
});

test('default dependency list is canonical unique bounded and ends at the primary group', async () => {
  for (const sourceGroups of [[], ['41', '41'], ['0', '42'], [41, '42'], ['41'],
    Array.from({length: 9}, (_, index) => String(index + 1)), '42']) {
    const f = fixture();
    assert.equal(f.controller.observe(observation({authority: 'default', group: '42',
      data: {sourceGroups}, groupEnd: true})), null); await flush();
    assert.equal(f.sent.length, 0); assert.equal(f.controller.state().status, 'suspended');
    assert.match(f.resync.at(-1).reason, /source depend|identifier/i);
  }
  const f = fixture();
  assert.equal(f.controller.observe(observation({data: {sourceGroups: ['42']}})), null); await flush();
  assert.equal(f.sent.length, 0); assert.equal(f.controller.state().status, 'suspended');
});

test('omitted source groups retain the primary-only owner dependency', async () => {
  const f = fixture(); f.controller.observe(key());
  f.controller.observe(observation({authority: 'default', group: wide, groupEnd: true})); await flush();
  assert.deepEqual(f.sent[0].defaultDependencies, []);
  f.resolve(0, basis({token: '2'}), {defaultToken: {group: wide, token: maximum}}); await flush();
  assert.deepEqual(f.sent[1].defaultDependencies, [{group: wide, token: maximum}]);
  assert.equal(f.sent[1].defaultToken, maximum);
  f.resolve(1, basis({token: '3', value: 'abcX'})); await flush(); assert.equal(f.controller.state().status, 'ready');
});

test('pending composition cannot attest an already-live nonzero native transaction', async () => {
  const f = fixture({initial: basis({first: 1})});
  f.controller.observe(ime('begin', native('abc', 1), native('abc', 1))); await flush();
  f.resolve(0, basis({token: '2', first: 1, composition: wide}), {composition: {transaction: wide, state: 'pending'}});
  await flush(); terminal(f, 1); assert.equal(f.controller.state().unresolved, f.sent[0]);
});

test('a raw key cannot invent a nonzero native transaction without continuity', async () => {
  const f = fixture(); f.controller.observe(key()); await flush();
  f.resolve(0, basis({token: '2', composition: wide})); await flush(); terminal(f, 1);
});

for (const operation of ['key', 'nonempty-update']) test(`live composition cannot demote to pending through ${operation}`, async () => {
  const f = fixture({initial: basis({first: 1})});
  f.controller.observe(ime('begin', native('abc', 1), native('abc', 1))); await flush();
  f.resolve(0, basis({token: '2', first: 1, composition: wide}), {composition: {transaction: wide, state: 'live'}}); await flush();
  f.controller.observe(operation === 'key' ? key({before: native('abc', 1)}) : ime('update', native('abc', 1), native('aébc', 2)));
  await flush(); f.resolve(1, basis({token: '3', first: 1}), {composition: {transaction: wide, state: 'pending'}});
  await flush(); terminal(f, 2); assert.equal(f.controller.state().unresolved, f.sent[1]);
});

test('empty live composition update may become pending and then resume the same transaction', async () => {
  const f = fixture({initial: basis({first: 1})}), empty = ime('update', native('abc', 1), native('abc', 1)); empty.data.text = '';
  f.controller.observe(ime('begin', native('abc', 1), native('abc', 1))); f.controller.observe(empty);
  f.controller.observe(ime('update', native('abc', 1), native('aébc', 2)));
  f.controller.observe(ime('commit', native('aébc', 2), native('aébc', 2))); await flush();
  f.resolve(0, basis({token: '2', first: 1, composition: wide}), {composition: {transaction: wide, state: 'live'}}); await flush();
  f.resolve(1, basis({token: '3', first: 1}), {composition: {transaction: wide, state: 'pending'}}); await flush();
  assert.equal(f.sent[2].basis.composition, '0'); assert.equal(f.sent[2].observation.transaction, wide);
  f.resolve(2, basis({token: '4', value: 'aébc', first: 2, composition: wide}), {composition: {transaction: wide, state: 'live'}}); await flush();
  f.resolve(3, basis({token: '5', value: 'aébc', first: 2}), {composition: {transaction: wide, state: 'ended'}}); await flush();
  assert.equal(f.controller.state().status, 'ready'); assert.equal(f.controller.state().pending, 0);
  assert.equal(f.controller.state().basis.composition, '0'); assert.equal(f.failures.length, 0);
});

test('out-of-order IME and ordinary input reject before exporting an admitted unsent composition', async () => {
  for (const fault of ['update-first', 'end-first', 'double-begin', 'text', 'selection']) {
    const f = fixture({initial: basis({first: 1})});
    if (!fault.endsWith('first')) f.controller.observe(ime('begin', native('abc', 1), native('abc', 1)));
    const invalid = fault === 'update-first' ? ime('update', native('abc', 1), native('aébc', 2)) :
      fault === 'end-first' ? ime('commit', native('abc', 1), native('abc', 1)) :
      fault === 'double-begin' ? ime('begin', native('abc', 1), native('abc', 1)) :
      observation({kind: fault === 'text' ? 'text' : 'selection', before: native('abc', 1), after: native('abc', 1)});
    assert.equal(f.controller.observe(invalid), null); await flush(); assert.equal(f.sent.length, 0);
    assert.equal(f.controller.state().status, 'suspended'); assert.equal(f.failures.length, 0);
  }
});

test('queued composition end permits a fresh later transaction in the same ordered burst', async () => {
  const f = fixture({initial: basis({first: 1})});
  f.controller.observe(ime('begin', native('abc', 1), native('abc', 1)));
  f.controller.observe(ime('cancel', native('abc', 1), native('abc', 1)));
  f.controller.observe(ime('begin', native('abc', 1), native('abc', 1), '42'));
  f.controller.observe(ime('cancel', native('abc', 1), native('abc', 1), '42')); await flush();
  for (const [index, transaction, state] of [[0, wide, 'pending'], [1, wide, 'ended'], [2, '42', 'pending'], [3, '42', 'ended']]) {
    assert.equal(f.sent[index].observation.transaction, transaction);
    f.resolve(index, basis({token: String(index + 2), first: 1}), {composition: {transaction, state}}); await flush();
  }
  assert.equal(f.controller.state().status, 'ready'); assert.equal(f.controller.state().pending, 0); assert.equal(f.failures.length, 0);
});

test('basis publication callback failure retains its exact checked flight for diagnosis', async () => {
  for (const outcome of ['applied', 'rejected']) {
    const f = fixture({onBasis(value, metadata) { if (metadata.settled) throw Error('native publication failed'); }});
    f.controller.observe(key()); f.controller.observe(key({group: '42'})); await flush();
    f.resolve(0, basis({token: '2'}), {outcome}); await flush(); terminal(f, 1);
    assert.equal(f.controller.state().unresolved, f.sent[0]);
  }
});

// Lifecycle successor: the original58 functions and assertions are unchanged.
for (const ending of ['rejected', 'replaced']) for (const action of ['close', 'retire', 'activate'])
  test(`${ending} basis callback ${action} prevents stale receipt resynchronization`, async () => {
    let f, acted = false, nestedActivation;
    f = fixture({onBasis(value, metadata) {
      if (!metadata.settled || acted) return;
      acted = true;
      if (action === 'close') f.controller.close();
      else if (action === 'retire') f.controller.retire('publication callback retired');
      else nestedActivation = f.controller.activate(basis({token: '9', context: '99'}));
    }});
    f.controller.observe(key()); f.controller.observe(key({group: '42'})); await flush();
    f.resolve(0, basis({token: '2', context: ending === 'replaced' ? '88' : '7'}),
      ending === 'replaced' ? {continuity: 'replaced'} : {outcome: 'rejected'}); await flush();
    assert.equal(acted, true); assert.equal(f.sent.length, 1); assert.equal(f.failures.length, 0);
    if (action === 'retire') {
      assert.equal(f.controller.state().status, 'suspended');
      assert.deepEqual(f.resync.map(value => value.reason), ['publication callback retired']);
      assert.equal(f.controller.observe(key()), null);
    } else {
      assert.equal(f.resync.length, 0, 'An obsolete receipt cannot notify a successor or closed callback');
      assert.equal(f.controller.state().status, action === 'close' ? 'closed' : 'ready');
      if (action === 'close') {
        assert.equal(f.controller.observe(key()), null); assert.equal(f.controller.activate(basis()), false);
      } else {
        assert.equal(nestedActivation, true); assert.equal(f.controller.state().basis.token, '9');
        assert.equal(f.controller.observe(key()), '3'); await flush();
        assert.equal(f.sent.length, 2); assert.equal(f.sent[1].basis.identity.context, '99');
        assert.equal(f.sent[1].observation.predecessor, null);
        f.resolve(1, basis({token: '10', context: '99'})); await flush();
        assert.equal(f.controller.state().status, 'ready'); assert.equal(f.controller.state().basis.token, '10');
        assert.equal(f.resync.length, 0);
      }
    }
  });

for (const action of ['close', 'retire', 'activate', 'reactivate'])
  test(`activate reports its own incarnation was superseded when its callback does ${action}`, () => {
    let f, acted = false, nestedActivation;
    f = fixture({activate: false, onBasis(value, metadata) {
      if (metadata.settled || acted) return;
      acted = true;
      if (action === 'close') f.controller.close();
      else if (action === 'retire') f.controller.retire('activation callback retired');
      else {
        if (action === 'reactivate') f.controller.retire('fresh same-basis session');
        nestedActivation = f.controller.activate(action === 'reactivate' ? basis() : basis({token: '9', context: '99'}));
      }
    }});
    assert.equal(f.controller.activate(basis()), false);
    assert.equal(acted, true); assert.equal(f.sent.length, 0); assert.equal(f.failures.length, 0);
    if (action === 'close') assert.equal(f.controller.state().status, 'closed');
    else if (action === 'retire') {
      assert.equal(f.controller.state().status, 'suspended');
      assert.deepEqual(f.resync.map(value => value.reason), ['activation callback retired']);
    } else {
      assert.equal(nestedActivation, true); assert.equal(f.controller.state().status, 'ready');
      assert.equal(f.controller.state().session, '2');
      assert.equal(f.controller.state().basis.token, action === 'reactivate' ? '1' : '9');
      assert.equal(f.resync.length, action === 'reactivate' ? 1 : 0);
    }
  });

// Known-null successor: an authoritative native readback can retire the editor;
// it cannot supply a replacement range or authorize an old keyboard default.
const retirement = (packet, changes = {}) => ({availability: 'noneditable', identity: clone(packet.basis.identity),
  observationRevision: maximum, readbackAttested: true, ...changes});
const retiredReceipt = (packet, changes = {}) => receipt(packet, null, {outcome: 'cancelled', continuity: 'replaced',
  retirement: retirement(packet), ...changes});

for (const outcome of ['applied', 'cancelled', 'rejected']) for (const availability of ['noneditable', 'unavailable'])
  test(`${outcome} checked ${availability} readback suspends without projecting a null editor`, async () => {
    const f = fixture(); f.controller.observe(key()); f.controller.observe(key({group: '42'})); await flush();
    const proof = retirement(f.sent[0], {availability});
    proof.identity.context = maximum; proof.identity.presentationRevision = '3';
    f.pending[0].resolve(retiredReceipt(f.sent[0], {outcome, retirement: proof})); await flush();
    assert.equal(f.controller.state().status, 'suspended'); assert.equal(f.controller.state().basis, null);
    assert.equal(f.controller.state().pending, 0); assert.equal(f.controller.state().bytes, 0);
    assert.equal(f.sent.length, 1); assert.equal(f.failures.length, 0); assert.equal(f.accepted.length, 1);
    assert.deepEqual(f.resync, [{reason: `Editor ${outcome}`, value: null}]);
    assert.equal(f.controller.observe(key()), null);
  });

test('a checked null retirement drops dependent defaults, predecessor and admitted preedit', async () => {
  const f = fixture(); f.controller.observe(key());
  f.controller.observe(observation({authority: 'default', group: wide, groupEnd: true}));
  f.controller.observe(ime('begin', native('abcX'), native('abcX'))); await flush();
  f.pending[0].resolve(retiredReceipt(f.sent[0])); await flush();
  assert.equal(f.sent.length, 1); assert.equal(f.controller.state().basis, null);
  assert.equal(f.controller.activate(basis({token: '9', context: '99'})), true);
  assert.equal(f.controller.observe(key({group: '42'})), '4'); await flush();
  assert.equal(f.sent[1].observation.predecessor, null);
  f.resolve(1, basis({token: '10', context: '99'})); await flush();
  f.controller.observe(observation({authority: 'default', group: wide, groupEnd: true})); await flush();
  assert.equal(f.sent.length, 2); assert.equal(f.controller.state().status, 'suspended');
  assert.match(f.resync.at(-1).reason, /default was not authorized/);
  assert.equal(f.controller.activate(basis({token: '11', context: '99'})), true);
  assert.equal(f.controller.observe(ime('update', native(), native('aébc', 2))), null);
  assert.equal(f.sent.length, 2); assert.match(f.resync.at(-1).reason, /composition ordering/);
});

test('malformed or uncorrelated null retirement retains the exact unresolved head', async () => {
  const faults = [
    value => { delete value.retirement; }, value => { value.retirement = null; },
    value => { value.outcome = 'invalid'; },
    ...['same', 'key-retarget', null].map(continuity => value => { value.continuity = continuity; }),
    value => { value.defaultToken = {group: wide, token: '2'}; },
    value => { value.composition = {transaction: wide, state: 'ended'}; },
    value => { delete value.defaultToken; }, value => { delete value.composition; },
    ...['available', '', null, 1].map(availability => value => { value.retirement.availability = availability; }),
    value => { value.retirement.readbackAttested = false; }, value => { delete value.retirement.readbackAttested; },
    ...['0', '01', '18446744073709551616', 1, null].map(revision => value => { value.retirement.observationRevision = revision; }),
    value => { value.retirement.extra = true; },
    value => { value.retirement.identity.extra = '1'; },
    value => { value.retirement.identity.owner.extra = '1'; },
    value => { value.retirement.identity.owner.id = 'other'; },
    value => { value.retirement.identity.owner.generation = '1'; },
    value => { value.retirement.identity.generation = '1'; },
    value => { value.retirement.identity.epoch = '1'; },
    value => { value.retirement.identity.context = '0'; },
    value => { value.retirement.identity.presentationRevision = '0'; },
    ...['session', 'id', 'predecessor', 'submittedToken'].map(field => value => { value[field] = '999'; })
  ];
  for (const fault of faults) {
    const f = fixture(); f.controller.observe(key()); f.controller.observe(key({group: '42'})); await flush();
    const value = retiredReceipt(f.sent[0]); fault(value); f.pending[0].resolve(value); await flush();
    terminal(f, 1); assert.equal(f.controller.state().unresolved, f.sent[0]); assert.equal(f.resync.length, 0);
  }
});

test('nonnull known receipt cannot carry retirement authority', async () => {
  const f = fixture(); f.controller.observe(key()); await flush();
  f.resolve(0, basis({token: '2'}), {retirement: retirement(f.sent[0])}); await flush();
  terminal(f, 1); assert.equal(f.controller.state().unresolved, f.sent[0]);
  const allowed = fixture(); allowed.controller.observe(key()); await flush();
  allowed.resolve(0, basis({token: '2'}), {retirement: null}); await flush();
  assert.equal(allowed.controller.state().status, 'ready'); assert.equal(allowed.failures.length, 0);
});

test('unknown null receipt remains terminal before retirement semantics are decoded', async () => {
  const f = fixture(); f.controller.observe(key()); await flush();
  f.pending[0].resolve(retiredReceipt(f.sent[0], {outcome: 'unknown', retirement: {availability: 'invalid'}})); await flush();
  terminal(f, 1); assert.match(f.failures[0].message, /consumed outcome is unknown/);
  assert.equal(f.controller.state().unresolved, f.sent[0]); assert.equal(f.resync.length, 0);
});

test('late checked null retirement cannot suspend or publish into a successor session', async () => {
  const f = fixture(); f.controller.observe(key()); await flush();
  assert.equal(f.controller.activate(basis({token: '9', context: '99'})), true);
  f.controller.observe(key({group: '42'})); await flush(); assert.equal(f.sent.length, 1);
  f.pending[0].resolve(retiredReceipt(f.sent[0])); await flush();
  assert.equal(f.sent.length, 2); assert.equal(f.controller.state().status, 'awaiting');
  assert.equal(f.sent[1].basis.token, '9'); assert.equal(f.sent[1].observation.predecessor, null);
  assert.equal(f.resync.length, 0); assert.equal(f.failures.length, 0);
  f.resolve(1, basis({token: '10', context: '99'})); await flush();
  assert.equal(f.controller.state().status, 'ready'); assert.equal(f.controller.state().basis.token, '10');
});

for (const action of ['close', 'retire', 'activate'])
  test(`known null resynchronization callback ${action} preserves its lifecycle transition`, async () => {
    let f, acted = false;
    f = fixture({onResync(reason, accepted) {
      if (accepted !== null || acted) return; acted = true;
      if (action === 'close') f.controller.close();
      else if (action === 'retire') f.controller.retire('nested retirement');
      else assert.equal(f.controller.activate(basis({token: '9', context: '99'})), true);
    }});
    f.controller.observe(key()); await flush(); f.pending[0].resolve(retiredReceipt(f.sent[0])); await flush();
    assert.equal(acted, true); assert.equal(f.failures.length, 0); assert.equal(f.sent.length, 1);
    assert.equal(f.controller.state().status, action === 'activate' ? 'ready' : action === 'close' ? 'closed' : 'suspended');
    assert.equal(f.controller.state().basis?.token ?? null, action === 'activate' ? '9' : null);
  });

test('known null resynchronization callback failure retains its checked flight', async () => {
  const f = fixture({onResync() { throw Error('retirement publication failed'); }});
  f.controller.observe(key()); await flush(); f.pending[0].resolve(retiredReceipt(f.sent[0])); await flush();
  terminal(f, 1); assert.equal(f.controller.state().unresolved, f.sent[0]);
});

test('known null metadata owns and freezes the exact native retirement proof', async () => {
  let metadata;
  const f = fixture({onResync(reason, accepted, value) { metadata = value; }});
  f.controller.observe(key()); await flush();
  const raw = retiredReceipt(f.sent[0]); f.pending[0].resolve(raw); await flush();
  raw.retirement.identity.context = '42'; raw.retirement.observationRevision = '2';
  assert.equal(metadata.receipt.retirement.identity.context, '7');
  assert.equal(metadata.receipt.retirement.observationRevision, maximum);
  assert.equal(metadata.receipt.submittedToken, f.sent[0].basis.token);
  for (const value of [metadata, metadata.receipt, metadata.receipt.retirement,
    metadata.receipt.retirement.identity, metadata.receipt.retirement.identity.owner]) assert.equal(Object.isFrozen(value), true);
  assert.equal(f.accepted.length, 1); assert.equal(f.failures.length, 0);
});

test('retirement proof getters never execute and a malformed old reply still terminates a successor', async () => {
  for (const late of [false, true]) {
    const f = fixture(); f.controller.observe(key()); await flush();
    if (late) {
      assert.equal(f.controller.activate(basis({token: '9', context: '99'})), true);
      f.controller.observe(key({group: '42'}));
    }
    let reads = 0; const raw = retiredReceipt(f.sent[0]);
    Object.defineProperty(raw.retirement, 'readbackAttested', {enumerable: true, get() { ++reads; return true; }});
    f.pending[0].resolve(raw); await flush(); terminal(f, 1);
    assert.equal(reads, 0); assert.equal(f.controller.state().unresolved, f.sent[0]); assert.equal(f.resync.length, 0);
  }
});

// v5: effect outcome and local authority retirement are independent facts.
test('shared retirement copier owns exact legacy and authority-retired proof shapes', () => {
  const packet = {basis: basis()};
  for (const availability of ['noneditable', 'unavailable', 'available']) {
    const raw = retirement(packet, {availability, authorityRetired: true});
    raw.identity.context = maximum; raw.identity.presentationRevision = '2';
    const copied = copyEditorRetirement(raw, packet.basis.identity);
    raw.identity.context = '42'; raw.observationRevision = '1';
    assert.equal(copied.identity.context, maximum); assert.equal(copied.observationRevision, maximum);
    assert.equal(copied.authorityRetired, true); assert.equal(copied.availability, availability);
    for (const value of [copied, copied.identity, copied.identity.owner]) assert.equal(Object.isFrozen(value), true);
  }
  for (const availability of ['noneditable', 'unavailable'])
    assert.equal(copyEditorRetirement(retirement(packet, {availability})).availability, availability);
});

test('shared retirement copier rejects false, inferred, malformed or foreign authority', () => {
  const packet = {basis: basis()}, invalid = [
    retirement(packet, {availability: 'available'}),
    ...['noneditable', 'unavailable', 'available'].map(availability => retirement(packet, {availability, authorityRetired: false})),
    retirement(packet, {availability: 'available', authorityRetired: null}),
    retirement(packet, {availability: 'available', authorityRetired: true, extra: true}),
    retirement(packet, {availability: 'other', authorityRetired: true}),
    retirement(packet, {readbackAttested: false}), retirement(packet, {observationRevision: '0'})
  ];
  for (const value of invalid) assert.throws(() => copyEditorRetirement(value, packet.basis.identity));
  for (const field of ['generation', 'epoch']) {
    const original = clone(packet.basis.identity); original[field] = '99';
    assert.throws(() => copyEditorRetirement(retirement(packet), original));
  }
  for (const field of ['id', 'generation']) {
    const original = clone(packet.basis.identity); original.owner[field] = '99';
    assert.throws(() => copyEditorRetirement(retirement(packet), original));
  }
  let reads = 0; const getter = retirement(packet, {availability: 'available'});
  Object.defineProperty(getter, 'authorityRetired', {enumerable: true, get() { ++reads; return true; }});
  assert.throws(() => copyEditorRetirement(getter)); assert.equal(reads, 0);
  const original = clone(packet.basis.identity);
  Object.defineProperty(original, 'epoch', {enumerable: true, get() { ++reads; return '6'; }});
  assert.throws(() => copyEditorRetirement(retirement(packet), original)); assert.equal(reads, 0);
});

for (const outcome of ['applied', 'cancelled', 'rejected'])
  test(`${outcome} checked null may settle its exact locally suspended head`, async () => {
    let metadata;
    const f = fixture({onResync(reason, accepted, value) { if (accepted === null) metadata = value; }});
    f.controller.observe(key()); f.controller.observe(observation({authority: 'default', group: wide, groupEnd: true}));
    await flush(); const head = f.sent[0]; f.controller.retire('service retired local authority');
    assert.equal(f.controller.state().unresolved, head); assert.equal(f.controller.state().basis.token, '1');
    const proof = retirement(head, outcome === 'applied' ? {availability: 'available', authorityRetired: true} : {});
    f.pending[0].resolve(retiredReceipt(head, {outcome, retirement: proof})); await flush();
    assert.equal(f.controller.state().status, 'suspended'); assert.equal(f.controller.state().basis, null);
    assert.equal(f.controller.state().pending, 0); assert.equal(f.controller.state().bytes, 0);
    assert.equal(f.controller.state().unresolved, head); assert.equal(f.sent.length, 1); assert.equal(f.failures.length, 0);
    assert.equal(metadata.receipt.outcome, outcome); assert.equal(metadata.receipt.submittedToken, head.basis.token);
    assert.equal(f.resync.length, 2); assert.equal(f.accepted.length, 1); assert.equal(f.controller.observe(key()), null);
    assert.equal(f.controller.activate(basis({token: '9', context: '99'})), true);
    f.controller.observe(key({group: '42'})); await flush(); assert.equal(f.sent[1].observation.predecessor, null);
    f.resolve(1, basis({token: '10', context: '99'})); await flush(); assert.equal(f.controller.state().status, 'ready');
  });

test('local suspension does not permit a late nonnull receipt to republish its old basis', async () => {
  const f = fixture(); f.controller.observe(key()); await flush(); f.controller.retire('local suspension');
  f.resolve(0, basis({token: '2'})); await flush();
  assert.equal(f.controller.state().status, 'suspended'); assert.equal(f.controller.state().basis.token, '1');
  assert.equal(f.accepted.length, 1); assert.equal(f.resync.length, 1); assert.equal(f.failures.length, 0);
});

test('checked null cannot settle into a locally suspended successor activation', async () => {
  const f = fixture(); f.controller.observe(key()); await flush();
  assert.equal(f.controller.activate(basis({token: '9', context: '99'})), true);
  f.controller.retire('successor local suspension');
  f.pending[0].resolve(retiredReceipt(f.sent[0], {outcome: 'applied',
    retirement: retirement(f.sent[0], {availability: 'available', authorityRetired: true})})); await flush();
  assert.equal(f.controller.state().status, 'suspended'); assert.equal(f.controller.state().basis.token, '9');
  assert.equal(f.accepted.length, 2); assert.equal(f.resync.length, 1); assert.equal(f.failures.length, 0);
});

for (const fault of ['unknown', 'false-authority'])
  test(`${fault} reply after local suspension remains terminal with its exact head`, async () => {
    const f = fixture(); f.controller.observe(key()); await flush(); f.controller.retire('local suspension');
    const raw = retiredReceipt(f.sent[0], fault === 'unknown' ? {outcome: 'unknown', retirement: {invalid: true}} :
      {retirement: retirement(f.sent[0], {availability: 'available', authorityRetired: false})});
    f.pending[0].resolve(raw); await flush(); terminal(f, 1);
    assert.equal(f.controller.state().unresolved, f.sent[0]); assert.equal(f.resync.length, 1);
  });

// v7: a missing private publication pauses admission without retiring authority.
for (const source of ['composition-observation', 'logical-flight'])
  test(`null retirement preserves an actual ended fact from its ${source}`, async () => {
    let metadata;
    const f = fixture({onResync(reason, accepted, value) { if (accepted === null) metadata = value; }});
    f.controller.observe(ime('begin', native(), native())); await flush();
    let index = 0;
    if (source === 'logical-flight') {
      f.resolve(0, basis({token: '2', composition: wide}), {composition: {transaction: wide, state: 'live'}}); await flush();
      f.controller.observe(key()); await flush(); index = 1;
    }
    const ended = {transaction: wide, state: 'ended'};
    f.pending[index].resolve(retiredReceipt(f.sent[index], {outcome: 'applied', composition: ended})); await flush();
    assert.equal(f.controller.state().status, 'suspended'); assert.equal(f.controller.state().basis, null);
    assert.deepEqual(metadata.receipt.composition, ended); assert.equal(metadata.receipt.outcome, 'applied');
    assert.equal(f.failures.length, 0); assert.equal(f.sent.length, index + 1);
  });

test('null retirement rejects pending, live, foreign or nonexact composition facts', async () => {
  for (const composition of [{transaction: wide, state: 'pending'}, {transaction: wide, state: 'live'},
    {transaction: '42', state: 'ended'}, {transaction: wide, state: 'ended', extra: true},
    {state: 'ended'}, {transaction: '0', state: 'ended'}]) {
    const f = fixture(); f.controller.observe(ime('begin', native(), native())); await flush();
    f.pending[0].resolve(retiredReceipt(f.sent[0], {composition})); await flush();
    terminal(f, 1); assert.equal(f.controller.state().unresolved, f.sent[0]);
  }
});

test('pause before drain retains the queue and session while blocking new admission and publish bypass', async () => {
  const f = fixture(); f.controller.observe(key());
  f.controller.observe(observation({authority: 'default', group: wide, groupEnd: true}));
  const original = f.controller.state(); assert.equal(f.controller.pause(), true);
  assert.equal(f.controller.pause(), true); assert.equal(f.controller.state().paused, true);
  assert.equal(f.controller.observe(key({group: '42'})), null); await flush(); assert.equal(f.sent.length, 0);
  assert.equal(f.controller.state().pending, original.pending); assert.equal(f.controller.state().bytes, original.bytes);
  assert.equal(f.controller.state().session, original.session); assert.equal(f.controller.activate(original.basis), false);
  assert.equal(f.controller.resume(original.basis), true); await flush();
  assert.equal(f.sent.length, 1); assert.equal(f.sent[0].observation.id, '1'); assert.equal(f.accepted.length, 1);
  f.resolve(0, basis({token: '2'}), {defaultToken: {group: wide, token: '50'}}); await flush();
  assert.equal(f.sent.length, 2); assert.equal(f.sent[1].defaultToken, '50'); assert.equal(f.sent[1].observation.predecessor, '1');
  f.resolve(1, basis({token: '3', value: 'abcX'})); await flush();
  assert.equal(f.controller.state().pending, 0); assert.equal(f.controller.state().session, original.session);
  assert.equal(f.failures.length, 0); assert.equal(f.resync.length, 0);
});

test('an in-flight checked receipt settles while paused without draining or losing its default dependency', async () => {
  const f = fixture(); f.controller.observe(key());
  f.controller.observe(observation({authority: 'default', group: wide, groupEnd: true})); await flush();
  const head = f.sent[0], session = f.controller.state().session; assert.equal(f.controller.pause(), true);
  f.resolve(0, basis({token: '2', revision: '7'}), {defaultToken: {group: wide, token: '51'}}); await flush();
  assert.equal(f.controller.state().paused, true); assert.equal(f.controller.state().status, 'ready');
  assert.equal(f.controller.state().basis.token, '2'); assert.equal(f.controller.state().pending, 1); assert.equal(f.sent.length, 1);
  assert.equal(f.controller.resume(head.basis), false); assert.equal(f.controller.state().paused, true);
  assert.equal(f.controller.resume(f.controller.state().basis), true); await flush();
  assert.equal(f.sent.length, 2); assert.equal(f.sent[1].basis.token, '2'); assert.equal(f.sent[1].defaultToken, '51');
  assert.equal(f.sent[1].observation.predecessor, head.observation.id); assert.equal(f.controller.state().session, session);
  f.resolve(1, basis({token: '3', value: 'abcX'})); await flush(); assert.equal(f.failures.length, 0);
});

test('pause retains admitted preedit and native pending authority through its checked prefix', async () => {
  const f = fixture(); f.controller.observe(ime('begin', native(), native()));
  f.controller.observe(ime('update', native(), native('abcé')));
  f.controller.observe(ime('commit', native('abcé'), native('abcé'))); await flush();
  const session = f.controller.state().session; f.controller.pause();
  f.resolve(0, basis({token: '2'}), {composition: {transaction: wide, state: 'pending'}}); await flush();
  assert.equal(f.sent.length, 1); assert.equal(f.controller.state().pending, 2); assert.equal(f.controller.state().paused, true);
  assert.equal(f.controller.resume(f.controller.state().basis), true); await flush();
  assert.equal(f.sent[1].observation.transaction, wide); assert.equal(f.sent[1].observation.predecessor, '1');
  f.resolve(1, basis({token: '3', value: 'abcé', composition: wide}), {composition: {transaction: wide, state: 'live'}}); await flush();
  f.resolve(2, basis({token: '4', value: 'abcé'}), {composition: {transaction: wide, state: 'ended'}}); await flush();
  assert.equal(f.controller.state().session, session); assert.equal(f.controller.state().pending, 0);
  assert.equal(f.failures.length, 0); assert.equal(f.resync.length, 0);
});

test('resume requires the exact cached owned basis and real retirement clears the gate', () => {
  const f = fixture(), original = f.controller.state().basis; f.controller.pause();
  for (const mutate of [value => { value.token = '2'; }, value => { value.editorRevision = '2'; },
    value => { value.identity.presentationRevision = '2'; }, value => { value.identity.context = '2'; },
    value => { value.surrounding = 'xyz'; }, value => { value.selection = [0, 0]; },
    value => { value.backward = true; }, value => { value.composition = wide; }]) {
    const changed = clone(original); mutate(changed);
    assert.equal(f.controller.resume(changed), false); assert.equal(f.controller.state().paused, true);
    assert.equal(f.controller.state().basis, original);
  }
  assert.equal(f.controller.resume(null), false); assert.equal(f.resync.length, 0); assert.equal(f.accepted.length, 1);
  f.controller.retire('actual owner retirement'); assert.equal(f.controller.state().paused, false);
  assert.equal(f.controller.resume(original), false); assert.equal(f.controller.activate(basis({token: '9'})), true);
  assert.equal(f.controller.state().paused, false); assert.equal(f.controller.state().session, '2');
});

for (const outcome of ['applied', 'unknown']) test(`${outcome} retirement reply while paused preserves its actual terminal meaning`, async () => {
  const f = fixture(); f.controller.observe(ime('begin', native(), native())); await flush(); f.controller.pause();
  f.pending[0].resolve(retiredReceipt(f.sent[0], outcome === 'unknown' ? {outcome, composition: {invalid: true}} :
    {outcome, composition: {transaction: wide, state: 'ended'}})); await flush();
  assert.equal(f.controller.state().paused, false); assert.equal(f.sent.length, 1);
  if (outcome === 'unknown') { terminal(f, 1); assert.equal(f.controller.state().unresolved, f.sent[0]); }
  else { assert.equal(f.controller.state().status, 'suspended'); assert.equal(f.controller.state().basis, null); assert.equal(f.failures.length, 0); }
});
