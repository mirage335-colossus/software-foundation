import {surfaceScalarMap} from './browser_surface.mjs';
import {captureEditorText} from './browser_surface_editor_text.mjs';

const maximum = 18446744073709551615n, encoder = new TextEncoder();
const id = (value, nonzero = true) => {
  if (typeof value !== 'string' || !/^(0|[1-9][0-9]{0,19})$/.test(value) ||
      BigInt(value) > maximum || (nonzero && value === '0')) throw Error('Invalid editor identifier');
  return value;
};
const own = (value, budget = {bytes: 0, nodes: 0}, depth = 0) => {
  if (++budget.nodes > 256 || depth > 8) throw Error('Invalid editor data');
  if (value === null || typeof value === 'boolean') return value;
  if (typeof value === 'number' && Number.isSafeInteger(value)) return value;
  if (typeof value === 'string') {
    if (value.length > 65536) throw Error('Editor data limit');
    surfaceScalarMap(value); budget.bytes += encoder.encode(value).length;
    if (budget.bytes > 1048576) throw Error('Editor data limit');
    return value;
  }
  if (!value || typeof value !== 'object' || ![Object.prototype, null, Array.prototype].includes(Object.getPrototypeOf(value))) throw Error('Invalid editor data');
  const array = Array.isArray(value), out = array ? [] : {};
  if (array && value.length > 64) throw Error('Editor data limit');
  for (const key of Reflect.ownKeys(value)) {
    if (array && key === 'length') continue;
    const descriptor = Object.getOwnPropertyDescriptor(value, key);
    if (typeof key !== 'string' || key.length > 64 || !descriptor.enumerable || !Object.hasOwn(descriptor, 'value') ||
        (array && (!/^(0|[1-9][0-9]*)$/.test(key) || Number(key) >= value.length))) throw Error('Invalid editor data');
    Object.defineProperty(out, key, {value: own(descriptor.value, budget, depth + 1), enumerable: true});
  }
  if (array && Object.keys(out).length !== value.length) throw Error('Invalid editor data');
  return Object.freeze(out);
};
const context = basis => JSON.stringify([basis.identity.owner, basis.identity.generation, basis.identity.epoch, basis.identity.context]);
const projection = basis => {
  const map = surfaceScalarMap(basis.surrounding);
  return captureEditorText({value: basis.surrounding, selectionStart: map.utf16Offset(basis.selection[0]),
    selectionEnd: map.utf16Offset(basis.selection[1]), selectionDirection: basis.backward ? 'backward' : 'forward'});
};
const sameText = (a, b) => a.value === b.value && a.selectionStart === b.selectionStart &&
  a.selectionEnd === b.selectionEnd && (a.selectionDirection === 'backward') === (b.selectionDirection === 'backward');
const validateIdentity = identity => {
  if (!identity || !identity.owner || typeof identity.owner.id !== 'string' || !identity.owner.id ||
      encoder.encode(identity.owner.id).length > 128) throw Error('Invalid editor identity');
  id(identity.owner.generation);
  for (const key of ['presentationRevision', 'generation', 'epoch', 'context']) id(identity[key]);
};
const exact = (value, keys) => value && !Array.isArray(value) && Object.keys(value).length === keys.length &&
  keys.every(key => Object.hasOwn(value, key));
export function copyEditorBasis(value) {
  const basis = own(value);
  id(basis.token); id(basis.editorRevision); id(basis.composition, false); validateIdentity(basis.identity);
  if (typeof basis.backward !== 'boolean' || !Array.isArray(basis.selection) || basis.selection.length !== 2) throw Error('Invalid editor basis');
  projection(basis);
  return basis;
}
export function copyEditorRetirement(value, originalIdentity = null) {
  const retirement = own(value), authorityRetired = retirement && Object.hasOwn(retirement, 'authorityRetired');
  const keys = ['availability', 'identity', 'observationRevision', 'readbackAttested'];
  if (authorityRetired) keys.push('authorityRetired');
  if (!exact(retirement, keys) || retirement.readbackAttested !== true ||
      (authorityRetired && retirement.authorityRetired !== true) ||
      !(authorityRetired ? ['available', 'noneditable', 'unavailable'] : ['noneditable', 'unavailable']).includes(retirement.availability) ||
      !exact(retirement.identity, ['owner', 'presentationRevision', 'generation', 'epoch', 'context']) ||
      !exact(retirement.identity.owner, ['id', 'generation'])) throw Error('Invalid editor retirement');
  validateIdentity(retirement.identity); id(retirement.observationRevision);
  if (originalIdentity !== null) {
    const original = own(originalIdentity), identity = retirement.identity;
    validateIdentity(original);
    if (identity.owner.id !== original.owner.id || identity.owner.generation !== original.owner.generation ||
        identity.generation !== original.generation || identity.epoch !== original.epoch)
      throw Error('Unattested editor retirement');
  }
  return retirement;
}

// This private observation channel is deliberately separate from surfaceInput.
// Only the authoritative owner may turn it into Events with actual revisions.
export function createEditorObservationController({send, onBasis = () => {}, onResync = () => {},
  onFailure = () => {}, maxPending = 64, maxBytes = 1048576} = {}) {
  if (typeof send !== 'function' || ![onBasis, onResync, onFailure].every(v => typeof v === 'function') ||
      !Number.isSafeInteger(maxPending) || maxPending < 1 || maxPending > 64 ||
      !Number.isSafeInteger(maxBytes) || maxBytes < 1 || maxBytes > 1048576) throw Error('Invalid editor controller');
  let status = 'detached', basis = null, session = 0n, serial = 0n, queue = [], inFlight = null, outstanding = null,
    usedBytes = 0, predecessor = null, scheduled = false, composition = null, admittedComposition = null, publishing = null, unresolved = null, transition = 0n, paused = false;
  const defaults = new Map();
  const notify = (callback, ...args) => { try { callback(...args); } catch (error) { terminal(error); } };
  const discard = () => { queue = []; usedBytes = 0; defaults.clear(); composition = admittedComposition = null; };
  const terminal = (error, flight = outstanding ?? inFlight ?? publishing) => {
    if (status === 'closed' || status === 'terminal_unknown') return;
    unresolved = flight?.packet ?? unresolved; status = 'terminal_unknown'; paused = false; ++transition; discard();
    try { onFailure(error instanceof Error ? error : Error(String(error))); } catch {}
  };
  const suspend = (reason, next = basis) => {
    if (status === 'closed' || status === 'terminal_unknown') return;
    unresolved = inFlight?.packet ?? unresolved; inFlight = null; discard(); basis = next; status = 'suspended'; paused = false; ++transition;
    notify(onResync, reason, basis);
  };
  const schedule = () => {
    if (paused || scheduled || outstanding || status !== 'ready' || !queue.length) return;
    scheduled = true; queueMicrotask(() => { scheduled = false; drain(); });
  };
  const validateReceipt = (receipt, flight) => {
    receipt = own(receipt);
    if (receipt.session !== flight.packet.session || receipt.id !== flight.packet.observation.id ||
        receipt.predecessor !== flight.packet.observation.predecessor || receipt.submittedToken !== flight.packet.basis.token ||
        !['applied', 'cancelled', 'rejected', 'unknown'].includes(receipt.outcome)) throw Error('Mismatched editor receipt');
    if (receipt.outcome === 'unknown') return receipt;
    if (receipt.basis === null) {
      if (receipt.continuity !== 'replaced' || receipt.defaultToken !== null)
        throw Error('Invalid editor retirement');
      if (receipt.composition !== null) {
        const comp = receipt.composition, expected = flight.entry.observation.kind === 'composition' ?
          flight.entry.observation.transaction : flight.composition?.transaction;
        if (!exact(comp, ['transaction', 'state']) || comp.state !== 'ended' || !expected || comp.transaction !== expected)
          throw Error('Invalid retired composition continuity');
        id(comp.transaction);
      }
      return Object.freeze({...receipt, retirement: copyEditorRetirement(receipt.retirement, flight.packet.basis.identity)});
    }
    if (receipt.retirement !== undefined && receipt.retirement !== null) throw Error('Unexpected editor retirement');
    const next = copyEditorBasis(receipt.basis);
    if (!['same', 'key-retarget', 'replaced'].includes(receipt.continuity)) throw Error('Invalid editor continuity');
    if (receipt.continuity === 'same' && context(next) !== context(flight.packet.basis)) throw Error('Unattested editor retarget');
    if (receipt.continuity === 'key-retarget' && !['native', 'default'].includes(flight.entry.observation.authority)) throw Error('Unattested editor retarget');
    if (receipt.defaultToken !== null) {
      id(receipt.defaultToken.token); id(receipt.defaultToken.group);
      if (flight.entry.observation.kind !== 'key' || flight.entry.observation.data.phase !== 'down' ||
          receipt.defaultToken.group !== flight.entry.observation.group) throw Error('Invalid editor default token');
    }
    const comp = receipt.composition;
    if (comp !== null) {
      id(comp.transaction);
      const expected = flight.entry.observation.kind === 'composition' ? flight.entry.observation.transaction : flight.composition?.transaction;
      if (!['pending', 'live', 'ended'].includes(comp.state) || comp.transaction !== expected) throw Error('Invalid editor composition continuity');
      if (comp.state === 'live' && next.composition !== comp.transaction) throw Error('Missing native composition attestation');
      if (comp.state === 'pending' && (next.composition !== '0' || (flight.composition?.state === 'live' &&
          !(flight.entry.observation.kind === 'composition' && flight.entry.observation.data.operation === 'update' &&
            flight.entry.observation.data.text === '')))) throw Error('Invalid pending composition attestation');
      if (comp.state === 'ended' && next.composition !== '0') throw Error('Old native composition attestation');
    }
    if (comp === null && next.composition !== '0') throw Error('Unexplained native composition attestation');
    if (flight.composition && comp === null) throw Error('Missing native composition continuity');
    if (flight.entry.observation.kind === 'composition' && receipt.outcome === 'applied') {
      const ending = ['commit', 'cancel'].includes(flight.entry.observation.data.operation);
      if (!comp || (ending ? comp.state !== 'ended' : comp.state === 'ended')) throw Error('Missing composition receipt');
    }
    return {...receipt, basis: next};
  };
  const settle = (receipt, flight) => {
    // A replaced native incarnation never consumes its successor's state.
    if (session !== flight.session || ['closed', 'terminal_unknown'].includes(status)) return;
    const suspendedHead = receipt.basis === null && status === 'suspended' && inFlight === null && unresolved === flight.packet;
    if ((inFlight !== flight || status === 'suspended') && !suspendedHead) return;
    if (receipt.basis === null) {
      // A checked retirement ends the old local authority, even if a native
      // effect applied or local suspension preceded its settled owner reply.
      inFlight = null; basis = null; predecessor = null; discard(); status = 'suspended'; paused = false; ++transition;
      publishing = flight;
      notify(onResync, `Editor ${receipt.outcome}`, null, Object.freeze({settled: true, receipt}));
      publishing = null; return;
    }
    inFlight = null; usedBytes -= flight.entry.bytes; basis = receipt.basis;
    predecessor = flight.entry.observation.id;
    if (receipt.outcome !== 'applied' || receipt.continuity === 'replaced') {
      discard(); status = 'suspended'; paused = false; const marker = ++transition, accepted = basis;
      publishing = flight; notify(onBasis, accepted, {settled: true, preservePassage: false}); publishing = null;
      if (session === flight.session && transition === marker && status === 'suspended') notify(onResync, `Editor ${receipt.outcome}`, accepted);
      return;
    }
    if (receipt.defaultToken) {
      if (!defaults.has(receipt.defaultToken.group) && defaults.size >= maxPending) {
        suspend('Editor default group limit'); return;
      }
      defaults.set(receipt.defaultToken.group, receipt.defaultToken.token);
    }
    if (flight.entry.observation.authority === 'default' && flight.entry.observation.groupEnd)
      for (const group of flight.entry.observation.data.sourceGroups ?? [flight.entry.observation.group]) defaults.delete(group);
    if (flight.entry.observation.kind === 'key' && flight.entry.observation.groupEnd) defaults.delete(flight.entry.observation.group);
    if (receipt.composition) composition = receipt.composition.state === 'ended' ? null : receipt.composition;
    status = 'ready'; ++transition; publishing = flight;
    notify(onBasis, basis, {settled: true, preservePassage: queue.length > 0 || composition !== null}); publishing = null;
    schedule();
  };
  const drain = () => {
    if (paused || status !== 'ready' || outstanding || !queue.length) return;
    const entry = queue[0], observation = entry.observation;
    if (observation.authority === 'range' && (entry.context !== context(basis) || !sameText(observation.before, projection(basis)))) {
      suspend('Native predecessor projection changed'); return;
    }
    if (observation.authority === 'composition' && (!composition || composition.transaction !== observation.transaction)) {
      suspend('Native composition predecessor changed'); return;
    }
    const defaultDependencies = observation.authority === 'default' ?
      (observation.data.sourceGroups ?? [observation.group]).map(group => ({group, token: defaults.get(group)})) : [];
    const defaultToken = defaultDependencies.at(-1)?.token ?? null;
    if (defaultDependencies.some(value => !value.token)) { suspend('Keyboard default was not authorized'); return; }
    let packet;
    try { packet = own({type: 'editorObservation', session: String(session), basis,
      defaultToken: defaultToken ?? null, defaultDependencies, observation}); }
    catch (error) { suspend(error.message); return; }
    queue.shift();
    const flight = {session, entry, packet, composition}; inFlight = outstanding = flight; status = 'awaiting';
    let pending; try { pending = send(packet); } catch (error) { terminal(error); return; }
    Promise.resolve(pending).then(raw => {
      if (outstanding !== flight) return;
      outstanding = null;
      if (status === 'closed' || status === 'terminal_unknown') return;
      let receipt;
      try { receipt = validateReceipt(raw, flight); } catch (error) { terminal(error, flight); return; }
      if (receipt.outcome === 'unknown') { terminal(Error('Editor consumed outcome is unknown'), flight); return; }
      settle(receipt, flight); schedule();
    }, error => {
      if (outstanding === flight) { outstanding = null; terminal(error, flight); }
    });
  };
  return Object.freeze({
    activate(value) {
      if (paused || ['closed', 'terminal_unknown'].includes(status)) return false;
      const next = copyEditorBasis(value);
      if (basis && status !== 'suspended' && JSON.stringify(next) === JSON.stringify(basis)) return true;
      if (session === maximum) { terminal(Error('Editor session exhausted')); return false; }
      unresolved = inFlight?.packet ?? unresolved; inFlight = null; discard(); ++session;
      basis = next; predecessor = null; status = 'ready'; paused = false; const marker = ++transition, activeSession = session;
      notify(onBasis, basis, {settled: false, preservePassage: false});
      return status === 'ready' && transition === marker && session === activeSession && basis === next;
    },
    observe(value) {
      if (paused || !['ready', 'awaiting'].includes(status)) return null;
      if (serial === maximum) { terminal(Error('Editor observation exhausted')); return null; }
      try {
        value = own(value);
        if (!['key', 'text', 'selection', 'composition'].includes(value.kind) ||
            !['native', 'range', 'default', 'composition'].includes(value.authority) ||
            typeof value.groupEnd !== 'boolean') throw Error('Invalid editor observation');
        const group = value.group === null ? null : id(value.group), transaction = id(value.transaction, false);
        const before = captureEditorText(value.before), after = value.after === null ? null : captureEditorText(value.after);
        const data = own(value.data);
        if (value.kind === 'composition' ? transaction === '0' : transaction !== '0') throw Error('Invalid editor transaction');
        const allowed = value.kind === 'key' ? value.authority === 'native' && ['down', 'up'].includes(data.phase) :
          value.kind === 'selection' ? value.authority === 'range' :
          value.kind === 'text' ? ['range', 'default'].includes(value.authority) :
          ['begin', 'update', 'commit', 'cancel'].includes(data.operation) &&
            (data.operation === 'begin' ? ['range', 'default'].includes(value.authority) : value.authority === 'composition');
        if (!allowed) throw Error('Invalid editor observation authority');
        if (value.authority === 'default' && group === null) throw Error('Missing editor source group');
        if (data.sourceGroups !== undefined && (value.authority !== 'default' || !Array.isArray(data.sourceGroups) ||
            data.sourceGroups.length < 1 || data.sourceGroups.length > 8 || data.sourceGroups.at(-1) !== group ||
            new Set(data.sourceGroups.map(value => id(value))).size !== data.sourceGroups.length)) throw Error('Invalid editor source dependencies');
        if (value.kind === 'composition') {
          if (data.operation === 'begin' ? admittedComposition !== null : admittedComposition !== transaction) throw Error('Invalid editor composition ordering');
        } else if (admittedComposition !== null && value.kind !== 'key') throw Error('Composition owns editor input');
        const previous = queue.at(-1)?.observation.id ?? inFlight?.entry.observation.id ?? predecessor;
        const observation = own({id: String(serial + 1n), predecessor: previous, kind: value.kind, authority: value.authority,
          group, groupEnd: value.groupEnd, transaction, before, after, data});
        const bytes = encoder.encode(JSON.stringify(observation)).length;
        if (queue.length + Number(Boolean(outstanding)) >= maxPending || usedBytes + bytes +
            (outstanding && outstanding !== inFlight ? outstanding.entry.bytes : 0) > maxBytes) {
          suspend('Editor observation queue exhausted'); return null;
        }
        if (value.kind === 'composition') admittedComposition = ['commit', 'cancel'].includes(data.operation) ? null : transaction;
        ++serial; queue.push({observation, bytes, context: context(basis)}); usedBytes += bytes; schedule(); return observation.id;
      } catch (error) { suspend(error.message); return null; }
    },
    pause() { if (!['ready', 'awaiting'].includes(status) || !basis) return false; paused = true; return true; },
    resume(value) {
      if (!['ready', 'awaiting'].includes(status) || !basis) return false;
      let next; try { next = copyEditorBasis(value); } catch { return false; }
      if (JSON.stringify(next) !== JSON.stringify(basis)) return false;
      paused = false; schedule(); return true;
    },
    retire(reason = 'Editor retired') { suspend(reason); },
    close() { if (status !== 'closed') { unresolved = inFlight?.packet ?? publishing?.packet ?? unresolved; inFlight = null; discard(); status = 'closed'; paused = false; ++transition; } },
    state() { return Object.freeze({status, session: String(session), pending: queue.length + Number(Boolean(outstanding)),
      transition: String(transition), bytes: usedBytes, basis, paused, unresolved: unresolved ?? (status === 'terminal_unknown' ? inFlight?.packet ?? null : null)}); }
  });
}
