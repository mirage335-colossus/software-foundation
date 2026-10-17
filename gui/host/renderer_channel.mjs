import {MAX_OPERATION_BYTES,MAX_QUEUED_BYTES,MAX_CHANNEL_REQUESTS,MAX_STATE_BYTES,CHANNEL_PROTOCOL} from './browser_limits.mjs';

const encoder = new TextEncoder();
const uint = value => typeof value === 'string' && /^(0|[1-9][0-9]{0,19})$/.test(value) && BigInt(value) <= 18446744073709551615n;
const text = value => typeof value === 'string' && encoder.encode(value).length <= 65536;
const geometry = value => typeof value === 'number' && Number.isFinite(value) && Math.abs(value) <= 1000000;
const keyEqual = (a,b) => a?.id === b?.id && a?.generation === b?.generation;
const exact = (value, keys) => value && !Array.isArray(value) && typeof value === 'object' &&
  Object.keys(value).length === keys.length && keys.every(key => Object.hasOwn(value,key));
const requireShape = (value, keys) => { if (!exact(value,keys)) throw Error('Invalid renderer message shape'); };
const stale = message => { const error = Error(message); error.stale = true; throw error; };

export function clonePacket(value, maximum = MAX_OPERATION_BYTES) {
  let nodes = 0, characters = 0;
  const nodeLimit = maximum > MAX_OPERATION_BYTES ? 4 * 1024 * 1024 : 65536;
  const string = value => {
    characters += value.length;
    if (characters > maximum) throw Error('Renderer message exceeds byte limit');
  };
  const walk = (item,depth) => {
    if (++nodes > nodeLimit || depth > 24) throw Error('Renderer message exceeds structure limits');
    if (typeof item === 'string') { string(item); return; }
    if (item === null || typeof item === 'boolean') return;
    if (typeof item === 'number' && Number.isFinite(item)) return;
    if (typeof item !== 'object') throw Error('Renderer message contains unsupported data');
    const prototype = Object.getPrototypeOf(item);
    if (Array.isArray(item)) {
      // Reject sparse/huge arrays before stringify can expand holes into nulls.
      if (item.length > nodeLimit-nodes) throw Error('Renderer message exceeds structure limits');
      for (let index=0;index<item.length;++index) {
        if (!Object.hasOwn(item,index)) throw Error('Sparse renderer array');
        walk(item[index],depth+1);
      }
      let count=0;
      for (const name in item) if (Object.hasOwn(item,name) && ++count > item.length) throw Error('Invalid renderer array property');
    } else {
      if (prototype !== Object.prototype && prototype !== null) throw Error('Invalid renderer object');
      let count=0;
      for (const name in item) if (Object.hasOwn(item,name)) {
        if (++count > nodeLimit-nodes) throw Error('Renderer message exceeds structure limits');
        string(name); walk(item[name],depth+1);
      }
    }
  };
  walk(value,0);
  const serialized = JSON.stringify(value);
  if (serialized.length > maximum || encoder.encode(serialized).length > maximum) throw Error('Renderer message exceeds byte limit');
  return JSON.parse(serialized);
}

// Validate the delegated vocabulary before retaining it. Ordinary stale input
// has no transport side effect; malformed or unauthorized vocabulary is fatal.
export function validateRendererOperation(operation, snapshot, surface = undefined, surfaceProtocol = null, editorProtocol = null, editor = null, documentProtocol = null, documentState = null) {
  const descriptor = operation && typeof operation === 'object' && Object.getOwnPropertyDescriptor(operation,'type');
  if (descriptor && !Object.hasOwn(descriptor,'value')) throw Error('Invalid renderer operation discriminator');
  if (typeof descriptor?.value === 'string' && descriptor.value.startsWith('document')) {
    if (documentState === null || typeof documentProtocol?.validateDocumentOperation !== 'function') throw Error('Renderer operation is not delegated');
    return documentProtocol.validateDocumentOperation(operation,documentState);
  }
  if (typeof descriptor?.value === 'string' && descriptor.value.startsWith('editor')) {
    if (surface === undefined || typeof editorProtocol?.validateEditorOperation !== 'function') throw Error('Renderer operation is not delegated');
    return editorProtocol.validateEditorOperation(operation,snapshot,surface,editor);
  }
  if (typeof descriptor?.value === 'string' && descriptor.value.startsWith('surface')) {
    if (surface === undefined || typeof surfaceProtocol?.validateSurfaceOperation !== 'function') throw Error('Renderer operation is not delegated');
    return surfaceProtocol.validateSurfaceOperation(operation,snapshot,surface);
  }
  const schemas = {
    activate:['key'],checked:['key','value'],editIntent:['key','value'],choose:['key','id'],select:['key','id'],
    activateRecord:['key','id'],submit:['key'],action:['key','id'],pointer:['key','kind','pointerId','x','y','wheelX','wheelY','control','shift','alt'],
    focus:['key'],selection:['key','anchor','caret'],scroll:['key','x','y'],groupWheel:['key','x','y'],popupOpen:['key'],popupClose:['key'],
    popupChoice:['key','id'],listKey:['key','value'],page:['id'],shortcut:['key','control','shift','alt'],measure:['values']
  };
  if (!operation || !Object.hasOwn(schemas,operation.type)) throw Error('Renderer operation is not delegated');
  requireShape(operation,['type',...schemas[operation.type]]);
  const type = operation.type;
  if (['choose','select','activateRecord','action','popupChoice','page'].includes(type) && !text(operation.id)) throw Error('Invalid renderer item identity');
  if (['checked','shortcut','pointer'].includes(type)) {
    for (const name of type === 'checked' ? ['value'] : ['control','shift','alt'])
      if (typeof operation[name] !== 'boolean') throw Error('Invalid renderer boolean');
  }
  if (type === 'editIntent' && typeof operation.value !== 'string') throw Error('Invalid renderer edit');
  if (type === 'selection' && (!uint(operation.anchor) || !uint(operation.caret))) throw Error('Invalid renderer selection');
  if (type === 'scroll' && (!geometry(operation.x) || !geometry(operation.y) || operation.x < 0 || operation.y < 0)) throw Error('Invalid renderer scroll');
  if (type === 'groupWheel' && (!geometry(operation.x) || !geometry(operation.y))) throw Error('Invalid renderer group wheel');
  if (type === 'listKey' && !['up','down','space','enter'].includes(operation.value)) throw Error('Invalid renderer list key');
  if (type === 'pointer' && (!['press','release','cancel','double','move','wheel','context'].includes(operation.kind) ||
      !uint(operation.pointerId) || !['x','y','wheelX','wheelY'].every(name=>geometry(operation[name])) ||
      (['press','release','cancel'].includes(operation.kind) && operation.pointerId === '0') ||
      (operation.kind === 'context' && (operation.pointerId !== '0' || operation.wheelX !== 0 || operation.wheelY !== 0)))) throw Error('Invalid renderer pointer');
  if (type === 'shortcut' && (!Number.isInteger(operation.key) || operation.key < 0 || operation.key > 15)) throw Error('Invalid renderer shortcut');
  if (type === 'measure') {
    if (!Array.isArray(operation.values) || !operation.values.length || operation.values.length > 512) throw Error('Invalid renderer measurement batch');
    const seen = new Set();
    for (const value of operation.values) {
      requireShape(value,['id','width','height']);
      if (!uint(value.id) || seen.has(value.id) || !geometry(value.width) || !geometry(value.height) || value.width < 0 || value.height < 0)
        throw Error('Invalid renderer measurement');
      seen.add(value.id);
    }
  }
  if (!['measure','page','shortcut'].includes(type)) {
    requireShape(operation.key,['id','generation']);
    if (!text(operation.key.id) || !operation.key.id || !uint(operation.key.generation) || operation.key.generation === '0') throw Error('Invalid renderer widget identity');
  }
  if (!snapshot || snapshot.closed) stale('Application is closed');
  if (type === 'measure') {
    for (const value of operation.values) if (!snapshot.measurements.some(request=>request.id === value.id)) stale('Measurement request was replaced');
    return operation;
  }
  if (type === 'page') {
    if (!snapshot.pages.some(page=>page.id === operation.id && page.enabled)) stale('Page is no longer available');
    return operation;
  }
  if (type === 'shortcut') {
    if (!snapshot.keyBindings.some(binding=>['key','control','shift','alt'].every(name=>binding[name] === operation[name]))) stale('Shortcut is no longer available');
    return operation;
  }
  const widget = snapshot.widgets.find(widget=>keyEqual(widget.key,operation.key));
  if (!widget || !widget.visible || !widget.enabled || !widget.inModal) stale('Widget is no longer available');
  const kind = widget.kind;
  const kinds = {activate:[2],checked:[3],editIntent:[5],choose:[4,5,8],select:[6],activateRecord:[6],submit:[5],action:[7],selection:[5],scroll:[0,5,6],groupWheel:[0],listKey:[6]};
  if (kinds[type] && !kinds[type].includes(kind)) stale('Widget capability changed');
  if (['editIntent','submit'].includes(type) && widget.readOnly) stale('Editor is read only');
  if (type === 'submit' && !widget.submit) stale('Editor cannot submit');
  if (type === 'checked' && operation.value === widget.checked) stale('Toggle value is already current');
  if (type === 'choose' && ((kind === 5 && widget.readOnly) || !widget.options.some(option=>option.id === operation.id && option.enabled))) stale('Option is no longer available');
  if (['select','activateRecord'].includes(type) && !widget.records.some(record=>record.id === operation.id && record.enabled && (type !== 'activateRecord' || record.activatable))) stale('Record is no longer available');
  if (type === 'action' && !widget.actions.some(action=>action.id === operation.id && action.enabled)) stale('Action is no longer available');
  if (type === 'pointer' && !(operation.kind === 'context' ? widget.contextInput : widget.pointerInput)) stale('Pointer input is no longer available');
  if (type === 'pointer' && operation.kind === 'context' && snapshot.popup) stale('A popup owns context input');
  if (type === 'popupOpen' && !widget.actions?.some(action=>action.enabled)) stale('Popup is no longer available');
  if (['popupClose','popupChoice'].includes(type) && !keyEqual(snapshot.popup?.key,operation.key)) stale('Popup was replaced');
  if (type === 'popupChoice' && !snapshot.popup.options.some(option=>option.id === operation.id && option.enabled)) stale('Popup option was replaced');
  return operation;
}

export function publicSnapshot(snapshot) {
  const result = {};
  for (const name of ['revision','title','palette','width','height','scale','pages','activePage','widgets','measurements','keyBindings','commands','focus','popup','closed'])
    if (Object.hasOwn(snapshot,name)) result[name] = snapshot[name];
  return clonePacket(result,MAX_STATE_BYTES);
}

const packet = (generation,type,values={}) => ({protocol:CHANNEL_PROTOCOL,type,generation,...values});
const verify = (message,generation,keys) => {
  requireShape(message,['protocol','type','generation',...keys]);
  if (message.protocol !== CHANNEL_PROTOCOL || message.generation !== generation) throw Error('Renderer channel identity changed');
};
const coalesce = operation => {
  const suffix = operation.key && JSON.stringify([operation.key.id,operation.key.generation]);
  if (operation.type === 'editIntent') return `edit:${suffix}`;
  if (['selection','scroll'].includes(operation.type)) return `${operation.type}:${suffix}`;
  if (operation.type === 'pointer' && operation.kind === 'move') return `pointer:${suffix}`;
  return null;
};

export function createHostChannel({port,generation,client,onFailure=()=>{},onBound=()=>{},scheduler=globalThis,timeout=10000,surfaceProtocol=null,editorProtocol=null,documentProtocol=null}) {
  if (surfaceProtocol !== null && (typeof surfaceProtocol.validateSurfaceState !== 'function' || typeof surfaceProtocol.validateSurfaceOperation !== 'function')) throw Error('Invalid renderer surface protocol');
  if (editorProtocol !== null && (!surfaceProtocol || !['validateEditorPublication','validateEditorOperation','validateEditorReply'].every(name=>typeof editorProtocol[name]==='function'))) throw Error('Invalid renderer editor protocol');
  if (documentProtocol !== null && !['validateDocumentState','validateDocumentOperation','validateDocumentReply'].every(name=>typeof documentProtocol[name]==='function')) throw Error('Invalid renderer document protocol');
  let closed = false, bound = false, requestId = 0n, revision = 0n, acknowledged = 0n, inState = null, latest = null, timer = null, queuedBytes = 0, lastService = null, surfaceProfile = null, lastSurfaceBasis = null;
  const pending = new Map();
  const pairedProtocol=editorProtocol!==null||documentProtocol!==null;
  const pairedStates = []; let pairedStateBytes = 0;
  const clearTimer = () => { if (timer !== null) scheduler.clearTimeout(timer); timer = null; };
  const fail = error => { if (closed) return; close(); onFailure(error); };
  const post = value => { if (!closed) port.postMessage(value); };
  const flushResults = () => {
    for (const [id,result] of pending) {
      if (!result.finished || result.revision > acknowledged) break;
      post(packet(generation,'result',{id,ok:!result.error,error:result.error || '',...((result.editor||result.document)?{reply:result.reply??null}:{})}));
      queuedBytes -= result.bytes; pending.delete(id);
    }
  };
  const flushState = () => {
    if (!bound || closed || inState || (pairedProtocol?pairedStates.length===0:!latest)) return;
    if(pairedProtocol){const queued=pairedStates.shift();inState=queued.value;pairedStateBytes-=queued.bytes;}
    else {inState = latest; latest = null;}
    post(packet(generation,'state',inState));
    timer = scheduler.setTimeout(()=>fail(Error('Renderer did not acknowledge its state')),timeout);
  };
  const accept = state => {
    if (closed) return;
    try {
      const hasSurface = Object.hasOwn(state,'surface');
      if (surfaceProfile !== null && hasSurface !== surfaceProfile) throw Error('Renderer surface profile changed');
      if (hasSurface && surfaceProtocol === null) throw Error('Renderer surface profile is not enabled');
      const service = JSON.stringify(state.service ?? null), previous = pairedProtocol?pairedStates.at(-1)?.value:latest;
      const next = {revision:String(revision+1n),snapshot:publicSnapshot(state.snapshot),barrier:false,cancelPointers:Boolean(state.service) || Boolean(previous?.cancelPointers)};
      let basis = null;
      if (hasSurface) {
        const pair = clonePacket({snapshot:next.snapshot,surface:state.surface},MAX_STATE_BYTES);
        surfaceProtocol.validateSurfaceState(pair.snapshot,pair.surface);
        if (pair.surface !== null && state.service && !pair.surface.serviceActive) throw Error('Renderer surface service ownership changed');
        next.snapshot = pair.snapshot; next.surface = pair.surface;
        const p = pair.surface?.presentation;
        basis = JSON.stringify(p ? [p.identity.owner,p.identity.generation,p.identity.epoch,p.identity.context,p.bounds,p.clip,p.available] : null);
      }
      if(editorProtocol){
        if(!hasSurface||!Object.hasOwn(state,'editor')||!Object.hasOwn(state,'editorReply'))throw Error('Missing paired editor state');
        next.editor=editorProtocol.validateEditorPublication(next.snapshot,next.surface,state.editor);
        next.editorReply=state.editorReply===null?null:editorProtocol.validateEditorReply(state.editorReply);
      }
      if(documentProtocol){
        if(!Object.hasOwn(state,'document')||!Object.hasOwn(state,'documentReply'))throw Error('Missing paired document state');
        next.document=documentProtocol.validateDocumentState(state.document,next.snapshot);
        next.documentReply=state.documentReply===null?null:documentProtocol.validateDocumentReply(state.documentReply,null,state.ack);
      }else if(Object.hasOwn(state,'document')||Object.hasOwn(state,'documentReply'))throw Error('Renderer document profile is not enabled');
      next.barrier = revision === 0n || service !== lastService || Boolean(state.error) || Boolean(state.snapshot.closed) || basis !== lastSurfaceBasis || Boolean(previous?.barrier);
      surfaceProfile = hasSurface; lastService = service; lastSurfaceBasis = basis; ++revision;
      if(pairedProtocol){
        const bytes=encoder.encode(JSON.stringify(next)).length;
        if(bytes>MAX_STATE_BYTES||pairedStates.length>=MAX_CHANNEL_REQUESTS||pairedStateBytes+bytes>MAX_STATE_BYTES)throw Error('Paired state queue is full');
        pairedStates.push({value:next,bytes});pairedStateBytes+=bytes;
      }else latest = next;
      flushState();
    } catch (error) { fail(error); }
  };
  const receive = async event => {
    if (closed) return;
    try {
      if (event.ports?.length) throw Error('Unexpected renderer port');
      const message = clonePacket(event.data);
      if (!bound) {
        verify(message,generation,[]);
        if (message.type !== 'bound') throw Error('Renderer channel was not bound');
        bound = true; onBound(); flushState(); return;
      }
      if (message.type === 'stateAck') {
        verify(message,generation,['revision']);
        if (!uint(message.revision) || !inState || message.revision !== inState.revision) throw Error('Unexpected renderer state acknowledgment');
        acknowledged = BigInt(message.revision); inState = null; clearTimer(); flushResults(); flushState(); return;
      }
      verify(message,generation,['id','operation']);
      if (message.type !== 'request' || !uint(message.id) || BigInt(message.id) !== requestId+1n) throw Error('Unexpected renderer request identity');
      requestId = BigInt(message.id);
      const operation = message.operation;
      const bytes = operation?.type === 'editIntent' ? MAX_OPERATION_BYTES : encoder.encode(JSON.stringify(message)).length+512;
      if (pending.size >= MAX_CHANNEL_REQUESTS || queuedBytes+bytes > MAX_QUEUED_BYTES) throw Error('Renderer request queue is full');
      const editorOperation=typeof operation?.type==='string'&&operation.type.startsWith('editor');
      const documentOperation=typeof operation?.type==='string'&&operation.type.startsWith('document');
      const completion = {bytes,finished:false,revision:revision,error:'',editor:editorOperation,document:documentOperation}; pending.set(message.id,completion); queuedBytes += bytes;
      const check = state => {
        if (closed) throw Error('Renderer channel closed');
        const profile = Object.hasOwn(state,'surface');
        if (surfaceProfile !== null && profile !== surfaceProfile) throw Error('Renderer surface profile changed');
        if (profile && surfaceProtocol === null) throw Error('Renderer surface profile is not enabled');
        if (profile) surfaceProtocol.validateSurfaceState(state.snapshot,state.surface);
        validateRendererOperation(operation,state.snapshot,profile ? state.surface : undefined,surfaceProtocol,editorProtocol,state.editor,documentProtocol,state.document);
        if ((state.service || (profile && state.surface?.serviceActive)) && !['measure',...(editorProtocol?['editorTake','editorRevoke','editorResync']:[]),...(documentProtocol?['documentTake']:[])].includes(operation.type)) stale('A host service is active');
      };
      try {
        const profile = Object.hasOwn(client.state,'surface');
        if (surfaceProfile !== null && profile !== surfaceProfile) throw Error('Renderer surface profile changed');
        if (profile && surfaceProtocol === null) throw Error('Renderer surface profile is not enabled');
        if (profile) surfaceProtocol.validateSurfaceState(client.state.snapshot,client.state.surface);
        validateRendererOperation(operation,client.state.snapshot,profile ? client.state.surface : undefined,surfaceProtocol,editorProtocol,client.state.editor,documentProtocol,client.state.document);
        const prepared = operation.type === 'editIntent' ? snapshot=>({type:'edit',key:operation.key,value:operation.value,base:snapshot.widgets.find(widget=>keyEqual(widget.key,operation.key))?.text ?? ''}) : operation;
        const response=await client.send(prepared,coalesce(operation),check);
        if(editorOperation)completion.reply=editorProtocol.validateEditorReply(response.editorReply,operation,response.ack);
        if(documentOperation)completion.reply=documentProtocol.validateDocumentReply(response.documentReply,operation,response.ack);
        if (closed) return;
      } catch (error) {
        if (closed) return;
        if (!error.stale && !client.closed && !client.failed) throw error;
        completion.error = String(error.message || 'Renderer input was rejected').slice(0,1024);
        accept(client.state);
      }
      completion.finished = true; completion.revision = revision; flushResults(); flushState();
    } catch (error) { fail(error); }
  };
  const close = () => {
    if (closed) return; closed = true; clearTimer();
    pending.clear(); latest = null; inState = null; queuedBytes = 0;pairedStates.length=0;pairedStateBytes=0;
    port.onmessage = null; port.onmessageerror = null; port.close();
  };
  port.onmessage = receive; port.onmessageerror = ()=>fail(Error('Renderer message could not be decoded')); port.start?.();
  return {accept,close};
}

export function createRendererRequests({port,generation,acceptSnapshot,present,onFailure=()=>{},surfaceProtocol=null,editorProtocol=null,documentProtocol=null}) {
  if (surfaceProtocol !== null && (typeof surfaceProtocol.validateSurfaceState !== 'function' || typeof surfaceProtocol.validateSurfaceOperation !== 'function')) throw Error('Invalid renderer surface protocol');
  if (editorProtocol !== null && (!surfaceProtocol || !['validateEditorPublication','validateEditorOperation','validateEditorReply'].every(name=>typeof editorProtocol[name]==='function'))) throw Error('Invalid renderer editor protocol');
  if (documentProtocol !== null && !['validateDocumentState','validateDocumentOperation','validateDocumentReply'].every(name=>typeof documentProtocol[name]==='function')) throw Error('Invalid renderer document protocol');
  let closed = false, nextId = 0n, revision = 0n, queuedBytes = 0, surfaceProfile = null;
  const pending = new Map();
  const close = (error=Error('Renderer channel closed')) => {
    if (closed) return; closed = true;
    for (const completion of pending.values()) completion.reject(error);
    pending.clear(); queuedBytes = 0; port.onmessage = null; port.onmessageerror = null; port.close();
  };
  const fail = error => { close(error); onFailure(error); };
  const send = operation => new Promise((resolve,reject)=>{
    if (closed) { reject(Error('Renderer channel closed')); return; }
    let copied, bytes;
    try {
      copied = clonePacket(operation,MAX_OPERATION_BYTES-512);
      bytes = copied.type === 'editIntent' ? MAX_OPERATION_BYTES : encoder.encode(JSON.stringify(copied)).length+512;
      if (pending.size >= MAX_CHANNEL_REQUESTS || queuedBytes+bytes > MAX_QUEUED_BYTES || nextId === 18446744073709551615n) throw Error('Renderer input queue is full');
    } catch (error) { reject(error); return; }
    const id = String(++nextId); pending.set(id,{resolve,reject,bytes,operation:copied,editor:typeof copied.type==='string'&&copied.type.startsWith('editor'),document:typeof copied.type==='string'&&copied.type.startsWith('document')}); queuedBytes += bytes;
    try { port.postMessage(packet(generation,'request',{id,operation:copied})); } catch (error) { fail(error); }
  });
  port.onmessage = event => {
    if (closed) return;
    try {
      if (event.ports?.length) throw Error('Unexpected host port');
      const message = clonePacket(event.data,MAX_STATE_BYTES);
      if (message.type === 'state') {
        const hasSurface = Object.hasOwn(message,'surface');
        verify(message,generation,['revision','snapshot','barrier','cancelPointers',...(hasSurface ? ['surface'] : []),...(editorProtocol?['editor','editorReply']:[]),...(documentProtocol?['document','documentReply']:[])]);
        if (!uint(message.revision) || BigInt(message.revision) <= revision || typeof message.barrier !== 'boolean' || typeof message.cancelPointers !== 'boolean') throw Error('Unexpected host state');
        if (surfaceProfile !== null && hasSurface !== surfaceProfile) throw Error('Renderer surface profile changed');
        if (hasSurface) {
          if (surfaceProtocol === null) throw Error('Renderer surface profile is not enabled');
          surfaceProtocol.validateSurfaceState(message.snapshot,message.surface);
        }
        if(editorProtocol){
          if(!hasSurface)throw Error('Missing editor surface state');
          editorProtocol.validateEditorPublication(message.snapshot,message.surface,message.editor);
          if(message.editorReply!==null)editorProtocol.validateEditorReply(message.editorReply);
        }
        if(documentProtocol){
          documentProtocol.validateDocumentState(message.document,message.snapshot);
          if(message.documentReply!==null)documentProtocol.validateDocumentReply(message.documentReply);
        }
        surfaceProfile = hasSurface;
        revision = BigInt(message.revision);
        // Accepted data is visible to edit/focus completions before painting.
        if (hasSurface) {
          if(documentProtocol)acceptSnapshot(message.snapshot,message.cancelPointers,message.surface,true,message.editor??null,message.editorReply??null,message.document,message.documentReply);
          else if(editorProtocol)acceptSnapshot(message.snapshot,message.cancelPointers,message.surface,true,message.editor,message.editorReply);
          else acceptSnapshot(message.snapshot,message.cancelPointers,message.surface,true);
          present(message.snapshot,message.barrier,message.surface,true);
        } else {
          if(documentProtocol)acceptSnapshot(message.snapshot,message.cancelPointers,null,false,null,null,message.document,message.documentReply);
          else acceptSnapshot(message.snapshot,message.cancelPointers);
          present(message.snapshot,message.barrier);
        }
        port.postMessage(packet(generation,'stateAck',{revision:message.revision})); return;
      }
      const completion = pending.get(message.id);
      verify(message,generation,['id','ok','error',...((completion?.editor||completion?.document)?['reply']:[])]);
      if (message.type !== 'result' || !uint(message.id) || typeof message.ok !== 'boolean' || typeof message.error !== 'string' || message.error.length > 1024) throw Error('Unexpected host completion');
      if (!completion || message.id !== pending.keys().next().value) throw Error('Unexpected host completion identity');
      const typedReply=message.ok?(completion.editor?editorProtocol.validateEditorReply(message.reply,completion.operation):completion.document?documentProtocol.validateDocumentReply(message.reply,completion.operation):null):null;
      pending.delete(message.id); queuedBytes -= completion.bytes;
      if (message.ok) completion.resolve(completion.editor||completion.document?typedReply:{}); else { const error = Error(message.error); error.stale = true; completion.reject(error); }
    } catch (error) { fail(error); }
  };
  port.onmessageerror = ()=>fail(Error('Host message could not be decoded')); port.start?.();
  port.postMessage(packet(generation,'bound'));
  return {send,close};
}
