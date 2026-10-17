import {createBrowserSurface} from './browser_surface.mjs';
import {createBrowserEditorConduit} from './browser_surface_editor.mjs';
import {copyEditorBasis, copyEditorRetirement} from './browser_surface_editor_controller.mjs';

const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const sameOwner = (a, b) => a?.id === b?.id && a?.generation === b?.generation;
const sameIdentity = (a, b) => a && b && sameOwner(a.owner, b.owner) &&
  ['presentationRevision', 'generation', 'epoch', 'context'].every(key => a[key] === b[key]);
const maximum = 18446744073709551615n;
const data = (value, key) => {
  if (!value || typeof value !== 'object' || ![Object.prototype, null].includes(Object.getPrototypeOf(value))) throw Error('Invalid editor metadata');
  const descriptor = Object.getOwnPropertyDescriptor(value, key);
  if (!descriptor?.enumerable || !Object.hasOwn(descriptor, 'value')) throw Error('Invalid editor metadata');
  return descriptor.value;
};
const shape = (value, names) => {
  const keys = Reflect.ownKeys(value);
  if (keys.length !== names.length || keys.some(key => !names.includes(key))) throw Error('Invalid editor metadata');
  for (const key of names) data(value, key);
};
const identifier = value => {
  if (typeof value !== 'string' || !/^[1-9][0-9]{0,19}$/.test(value) || BigInt(value) > maximum) throw Error('Invalid editor metadata identifier');
  return value;
};
const copyTag = value => Object.freeze({session: identifier(data(value, 'session')), id: identifier(data(value, 'id')),
  predecessor: data(value, 'predecessor') === null ? null : identifier(data(value, 'predecessor')),
  submittedToken: identifier(data(value, 'submittedToken'))});
const receiptProjection = value => {
  try {
    if (!['applied', 'cancelled', 'rejected'].includes(data(value, 'outcome'))) return null;
    const composition = data(value, 'composition'); let logical = null;
    if (composition !== null) {
      shape(composition, ['transaction', 'state']); const state = data(composition, 'state');
      if (!['pending', 'live', 'ended'].includes(state)) return null;
      const transaction = identifier(data(composition, 'transaction')); logical = state === 'ended' ? null : transaction;
    }
    const basis = data(value, 'basis');
    return {tag: copyTag(value), basis: basis === null ? null : copyEditorBasis(basis), logical,
      retirement: basis === null ? copyEditorRetirement(data(value, 'retirement')) : null};
  } catch { return null; }
};
const correlation = packet => ({session: packet.session, id: packet.observation.id,
  predecessor: packet.observation.predecessor, submittedToken: packet.basis.token});
const matches = (value, tag) => value && tag && ['session', 'id', 'predecessor', 'submittedToken'].every(key => value[key] === tag[key]);
const nativeProjection = basis => ({token: basis.token, owner: [basis.identity.owner.id, basis.identity.owner.generation],
  generation: basis.identity.generation, epoch: basis.identity.epoch, context: basis.identity.context,
  editorRevision: basis.editorRevision, surrounding: basis.surrounding, selection: basis.selection,
  backward: basis.backward, composition: basis.composition});
const sameNative = (a, b) => a && b && same(nativeProjection(a), nativeProjection(b));
const sameCore = (a, b) => a && b && sameOwner(a.owner, b.owner) &&
  ['generation', 'epoch', 'context'].every(key => a[key] === b[key]);
const retirementProjection = value => [value.availability, value.identity.owner.id, value.identity.owner.generation,
  ...['presentationRevision', 'generation', 'epoch', 'context'].map(key => value.identity[key]),
  value.observationRevision, value.readbackAttested, value.authorityRetired ?? null];
const sameRetirement = (a, b) => a && b && same(retirementProjection(a), retirementProjection(b));
const join = (basis, presentation) => {
  const editor = presentation.editor;
  if (!sameIdentity(basis.identity, presentation.identity) || basis.editorRevision !== editor.revision ||
      basis.surrounding !== editor.surrounding || !same(basis.selection, editor.selection) ||
      basis.backward !== editor.selectionBackward || basis.composition !== editor.compositionTransaction)
    throw Error('Editor projection does not match the accepted surface');
};

// Separate endpoint injection keeps observations out of the ordinary surfaceInput
// policy. Tokens and settlements come from the owner after native readback and
// safe publication; the browser never invents an editor revision or token.
export function createBrowserEditorSurface(options = {}) {
  const endpoint = options.editor;
  if (!endpoint || !['resolveBasis', 'sendObservation', 'revoke', 'resync'].every(key => typeof endpoint[key] === 'function') ||
      (endpoint.trace !== undefined && typeof endpoint.trace !== 'function')) throw Error('Editor surface requires an authoritative endpoint');
  const createBridge = ({root, document, onFailure}) => {
    const ownedNodes = new WeakSet();
    let closed = false, terminal = false, publication = 0n, view = null, flight = null, latest = null, logicalComposition = null, retiredBasis = null, bodyIdentity = null;
    const remember = () => { const node = conduit.element(); if (node) ownedNodes.add(node); };
    const fail = error => {
      if (closed) return;
      terminal = closed = true; bodyIdentity = null; ++publication; remember(); conduit.close(); onFailure(error);
    };
    const conduit = createBrowserEditorConduit({root, document,
      send(packet) {
        const current = {packet, tag: correlation(packet)}; flight = current;
        let pending;
        try { pending = endpoint.sendObservation(packet); } catch (error) { throw error; }
        return Promise.resolve(pending).then(receipt => {
          // Descriptor-only copies never invoke receipt accessors. Keep the
          // outstanding head staged until the controller validates its receipt.
          const projected = receiptProjection(receipt);
          // Run after the controller's receipt reaction, before its next drain.
          // This ordering joins publication; it grants no DOM event provenance.
          queueMicrotask(() => queueMicrotask(() => {
            if (flight === current) flight = null;
            const state = conduit.state();
            if (closed || state.session !== current.tag.session || !projected || !matches(projected.tag, current.tag) ||
                !(projected.basis === null ? state.basis === null && state.status === 'suspended' : sameNative(state.basis, projected.basis))) return;
            latest = projected; logicalComposition = projected.logical;
            if (!view || !matches(view.settlement, current.tag)) return;
            try { synchronize(view); } catch (error) { fail(error); }
          }));
          return receipt;
        });
      },
      onFailure: fail,
      onRevoke(record) { remember(); if (record.basis) retiredBasis = record.basis; bodyIdentity = null; if (!terminal) endpoint.revoke(record); },
      onResync(reason, basis, metadata) { if (!terminal) endpoint.resync(reason, basis, metadata); },
      onTrace(record) { remember(); if (!terminal) endpoint.trace?.(record); }
    });
    const synchronize = candidate => {
      if (closed || view !== candidate || !candidate.connected) return;
      const ticket = candidate.ticket, current = () => !closed && publication === ticket && view === candidate;
      const surface = candidate.surface, presentation = surface?.presentation, editor = presentation?.editor;
      bodyIdentity = null;
      if (surface === null) { remember(); conduit.retire('Editor surface unavailable'); return; }
      let resolved;
      try { resolved = endpoint.resolveBasis(structuredClone(candidate.snapshot), structuredClone(surface)); }
      catch (error) { if (current()) { remember(); conduit.retire('Editor projection resolver failed'); } throw error; }
      if (!current()) return;
      if (resolved === null) { remember(); conduit.retire('Editor projection unavailable'); return; }
      let pendingAdmission;
      try { pendingAdmission = Object.hasOwn(resolved, 'pending'); }
      catch (error) { if (current()) { remember(); conduit.retire('Invalid editor admission'); throw error; } return; }
      if (!current()) return;
      if (pendingAdmission) {
        try {
          shape(resolved, ['pending']);
          if (data(resolved, 'pending') !== true) throw Error('Invalid pending editor admission');
        } catch (error) { if (current()) { remember(); conduit.retire(error.message); throw error; } return; }
        if (!current()) return;
        const state = conduit.state();
        if (!editor || (BigInt(surface.capabilities.supported) & 63n) !== 63n || !surface.focused || !surface.active ||
            candidate.serviceActive || surface.serviceActive || !presentation.available || !editor.editable || candidate.snapshot.closed ||
            (state.basis && !sameCore(state.basis.identity, presentation.identity))) {
          remember(); conduit.retire('Pending editor surface unavailable'); return;
        }
        // Missing private publication authorizes no ingress or native cleanup.
        // Cached facts stay owned until a fresh checked projection joins them.
        candidate.pending = true; remember(); conduit.pause(); return;
      }
      let basis, settlement, retirement = null, nullProjection = false;
      try {
        const rawBasis = data(resolved, 'basis'); nullProjection = rawBasis === null;
        shape(resolved, rawBasis === null ? ['basis', 'settlement', 'retirement'] : ['basis', 'settlement']);
        settlement = data(resolved, 'settlement');
        if (settlement !== null) { shape(settlement, ['session', 'id', 'predecessor', 'submittedToken']); settlement = copyTag(settlement); }
        if (rawBasis === null) {
          const original = flight && matches(settlement, flight.tag) ? flight.packet.basis.identity : null;
          retirement = copyEditorRetirement(data(resolved, 'retirement'), original);
          basis = null;
        } else {
          basis = copyEditorBasis(rawBasis);
          if (!editor) throw Error('Editable projection has no public editor');
          join(basis, presentation);
        }
      } catch (error) {
        if (nullProjection && settlement && ((flight && matches(settlement, flight.tag)) || (latest && matches(settlement, latest.tag)))) { fail(error); return; }
        remember(); conduit.retire(error.message); if (current()) throw error; return;
      }
      if (!current()) return;
      candidate.settlement = settlement;
      const state = conduit.state();
      if (basis === null) {
        if (settlement !== null) {
          if (flight && state.session === flight.tag.session && matches(settlement, flight.tag) &&
              (!latest || !matches(latest.tag, settlement))) {
            // Redact immediately. The retained transport head may still settle
            // with its checked retirement in this same controller session.
            remember(); conduit.retire('Editor retirement publication pending receipt'); return;
          }
          if (!latest || state.session !== latest.tag.session || !matches(settlement, latest.tag)) {
            remember(); conduit.retire('Unmatched editor retirement settlement'); return;
          }
          if (latest.basis !== null || !sameRetirement(retirement, latest.retirement) || surface?.composition !== null) {
            fail(Error('Editor retirement publication differs from its receipt')); return;
          }
        }
        if (presentation && (!sameCore(retirement.identity, presentation.identity) || editor !== null || surface.composition !== null)) {
          fail(Error('Editor retirement does not match the accepted surface')); return;
        }
        remember();
        if (state.basis !== null || !['suspended', 'detached'].includes(state.status)) conduit.retire('Editor authority retired');
        if (!current()) return;
        logicalComposition = null;
        if (current() && !flight && retirement.availability === 'noneditable' && retirement.authorityRetired !== true && presentation?.available && surface.focused && surface.active &&
            !candidate.serviceActive && !surface.serviceActive && !candidate.snapshot.closed)
          bodyIdentity = presentation.identity;
        return;
      }
      if (!editor || (BigInt(surface.capabilities.supported) & 63n) !== 63n || !surface.focused || !surface.active ||
          candidate.serviceActive || surface.serviceActive || !presentation.available || !editor.editable) {
        remember(); conduit.retire('Editor surface unavailable'); return;
      }
      if (state.paused && flight && (settlement === null ||
          (state.session === flight.tag.session && matches(settlement, flight.tag)))) return;
      if (state.paused && !sameNative(basis, state.basis)) {
        const oldToken = state.basis?.token;
        remember(); conduit.retire('Checked editor projection changed during admission pause');
        if (!current() || basis.token === oldToken) return;
      }
      if (sameNative(basis, retiredBasis)) { remember(); conduit.retire('Retired editor token cannot be resumed'); return; }
      if (settlement !== null) {
        // A head-tagged projection may precede its checked receipt. Leave the
        // provisional textarea and predecessor chain intact until that receipt.
        if (flight && state.session === flight.tag.session && matches(settlement, flight.tag)) return;
        if (!latest || state.session !== latest.tag.session || !matches(settlement, latest.tag)) {
          remember(); conduit.retire('Unmatched editor settlement'); return;
        }
        if (!sameNative(basis, latest.basis) || surface.composition !== latest.logical) {
          fail(Error('Editor settlement projection differs from its receipt')); return;
        }
        if (['suspended', 'closed', 'terminal_unknown'].includes(state.status)) return;
      } else {
        if (state.status === 'suspended' && basis.token === state.basis?.token) return;
        if ((sameNative(basis, state.basis) && surface.composition !== logicalComposition) ||
            (!sameNative(basis, state.basis) && surface.composition !== null)) {
          remember(); conduit.retire('Unowned editor composition'); return;
        }
      }
      if (sameNative(basis, state.basis) && !['suspended', 'closed', 'terminal_unknown'].includes(state.status)) {
        // A presentation-only refresh does not change the owner's native token
        // or mapping. The endpoint accepts this old pRevision alias for that
        // exact token; ranges and native facts are never restamped here.
        basis = state.basis;
      }
      if (!current()) return;
      logicalComposition = surface.composition;
      remember();
      const options = {editable: editor.editable, focused: surface.focused, active: surface.active,
        serviceActive: candidate.serviceActive || surface.serviceActive, available: presentation.available,
        caret: editor.caret, clip: presentation.clip};
      if (conduit.state().paused) conduit.resume(basis, options);
      else conduit.publish(basis, options);
      remember();
    };
    return Object.freeze({
      accept(snapshot, surface, {serviceActive = false, connected = false} = {}) {
        if (closed) return;
        bodyIdentity = null;
        const candidate = {ticket: ++publication, snapshot, surface, serviceActive, connected}; view = candidate;
        synchronize(candidate);
      },
      focused(identity) { const node = conduit.element(), basis = conduit.state().basis;
        remember(); return !!node && document.activeElement === node && basis && identity &&
          sameOwner(identity.owner, basis.identity.owner) && ['generation', 'epoch', 'context'].every(key => identity[key] === basis.identity[key]); },
      allowsBodyKey(identity) { return !closed && bodyIdentity !== null && sameIdentity(bodyIdentity, identity); },
      ownsTarget(node) { remember(); return !!node && ownedNodes.has(node); },
      retire(reason) { if (!closed) { ++publication; view = null; bodyIdentity = null; remember(); conduit.retire(reason); } },
      close() { if (!closed) { closed = true; bodyIdentity = null; ++publication; remember(); conduit.close(); } }
    });
  };
  return createBrowserSurface({...options, profile: 'editor_v1', editor: {...endpoint, createBridge}});
}
