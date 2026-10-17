import {copyEditorBasis,copyEditorRetirement} from './browser_surface_editor_controller.mjs';
import {captureEditorText} from './browser_surface_editor_text.mjs';
import {validateSurfaceState} from './browser_surface_protocol.mjs';

const maximum = 18446744073709551615n, encoder = new TextEncoder();
const canonical = value => value===null||typeof value!=='object'?value:Array.isArray(value)?value.map(canonical):Object.fromEntries(Object.keys(value).sort().map(key=>[key,canonical(value[key])]));
const same = (a,b) => JSON.stringify(canonical(a)) === JSON.stringify(canonical(b));
const malformed = () => { throw Error('Invalid editor endpoint packet'); };
const stale = () => { const error=Error('Editor projection is no longer available');error.stale=true;throw error; };
const id = (value,zero=false) => {
  if(typeof value!=='string'||!/^(0|[1-9][0-9]{0,19})$/.test(value)||BigInt(value)>maximum||(!zero&&value==='0'))malformed();
  return value;
};
const nullable = value => value===null?null:id(value);
const integer = (value,max=65536) => {if(!Number.isSafeInteger(value)||value<0||value>max)malformed();};
const text = (value,max=65536) => {if(typeof value!=='string'||encoder.encode(value).length>max)malformed();captureEditorText({value,selectionStart:0,selectionEnd:0,selectionDirection:'none'},max);};
const shape = (value,keys) => {if(!value||Array.isArray(value)||typeof value!=='object'||Object.keys(value).length!==keys.length||keys.some(key=>!Object.hasOwn(value,key)))malformed();};
const owned = value => {
  const budget={nodes:0,bytes:0};
  const copy=(item,depth=0)=>{
    if(++budget.nodes>4096||depth>16)malformed();
    if(item===null||typeof item==='boolean')return item;
    if(typeof item==='number'){if(!Number.isFinite(item))malformed();return item;}
    if(typeof item==='string'){budget.bytes+=encoder.encode(item).length;if(budget.bytes>1048576)malformed();return item;}
    if(!item||typeof item!=='object'||![Object.prototype,null,Array.prototype].includes(Object.getPrototypeOf(item)))malformed();
    const array=Array.isArray(item),out=array?[]:{};
    if(array&&item.length>256)malformed();
    for(const key of Reflect.ownKeys(item)){
      if(array&&key==='length')continue;
      const d=Object.getOwnPropertyDescriptor(item,key);
      if(typeof key!=='string'||key.length>64||!d?.enumerable||!Object.hasOwn(d,'value')||(array&&(!/^(0|[1-9][0-9]*)$/.test(key)||Number(key)>=item.length)))malformed();
      Object.defineProperty(out,key,{value:copy(d.value,depth+1),enumerable:true});
    }
    if(array&&Object.keys(out).length!==item.length)malformed();
    return Object.freeze(out);
  };
  return copy(value);
};
const identity = value => {shape(value,['owner','presentationRevision','generation','epoch','context']);shape(value.owner,['id','generation']);text(value.owner.id,128);if(!value.owner.id)malformed();id(value.owner.generation);for(const key of ['presentationRevision','generation','epoch','context'])id(value[key]);};
const basis = value => {shape(value,['token','identity','editorRevision','surrounding','selection','backward','composition']);identity(value.identity);return copyEditorBasis(value);};
const nativeBasis = value => value===null?null:{...value,identity:{...value.identity,presentationRevision:'0'}};
const range = (value,source=null) => {
  if(!Array.isArray(value)||value.length!==2)malformed();integer(value[0]);integer(value[1]);if(value[0]>value[1])malformed();
  if(source!==null){const bytes=encoder.encode(source);if(value[1]>bytes.length||value.some(n=>n<bytes.length&&(bytes[n]&192)===128))malformed();}
};
const textObservation = value => {
  shape(value,['value','selectionStart','selectionEnd','selectionDirection','selection','byteLength']);
  const captured=captureEditorText(value);if(!same(captured.selection,value.selection)||captured.byteLength!==value.byteLength)malformed();
};
const key = (value,held=false) => {
  const grouped=held&&Object.hasOwn(value,'group');shape(value,['phase','key','code','location','modifiers','repeat','isComposing',...(grouped?['group']:[])]);
  if(!['down','up'].includes(value.phase)||(held&&value.phase!=='down')||typeof value.repeat!=='boolean'||typeof value.isComposing!=='boolean'||(value.phase==='up'&&value.repeat))malformed();
  text(value.key,64);text(value.code,64);if(!value.key||!/^[\x21-\x7e]*$/.test(value.code))malformed();integer(value.location,3);integer(value.modifiers,31);if(grouped)nullable(value.group);
};
const composition = value => {if(value===null)return;shape(value,['transaction','state']);id(value.transaction);if(!['pending','live','ended'].includes(value.state))malformed();};
const retirement = value => {
  if(value===null)return;
  copyEditorRetirement(value);
};
const tag = value => {shape(value,['session','id','predecessor','submittedToken']);id(value.session);id(value.id);nullable(value.predecessor);id(value.submittedToken);};
const receipt = value => {
  shape(value,['session','id','predecessor','submittedToken','outcome','basis','continuity','defaultToken','composition','retirement']);
  tag({session:value.session,id:value.id,predecessor:value.predecessor,submittedToken:value.submittedToken});
  if(!['applied','cancelled','rejected','unknown'].includes(value.outcome)||!['same','key-retarget','replaced'].includes(value.continuity))malformed();
  if(value.basis!==null)basis(value.basis);composition(value.composition);retirement(value.retirement);
  if(value.defaultToken!==null){shape(value.defaultToken,['group','token']);id(value.defaultToken.group);id(value.defaultToken.token);}
  if(value.basis!==null&&value.retirement!==null)malformed();
  if(value.basis===null&&value.outcome!=='unknown'&&(!['applied','cancelled','rejected'].includes(value.outcome)||value.continuity!=='replaced'||value.defaultToken!==null||(value.composition!==null&&value.composition.state!=='ended')||value.retirement===null))malformed();
};
const packet = value => {
  shape(value,['type','session','basis','defaultToken','defaultDependencies','observation']);if(value.type!=='editorObservation')malformed();id(value.session);basis(value.basis);nullable(value.defaultToken);
  if(!Array.isArray(value.defaultDependencies)||value.defaultDependencies.length>8)malformed();const groups=new Set();
  for(const dep of value.defaultDependencies){shape(dep,['group','token']);id(dep.group);id(dep.token);if(groups.has(dep.group))malformed();groups.add(dep.group);}
  const o=value.observation;shape(o,['id','predecessor','kind','authority','group','groupEnd','transaction','before','after','data']);id(o.id);nullable(o.predecessor);nullable(o.group);id(o.transaction,true);
  if(typeof o.groupEnd!=='boolean'||!['native','range','default','composition'].includes(o.authority))malformed();textObservation(o.before);if(o.after!==null)textObservation(o.after);
  const data=o.data,hasGroups=Object.hasOwn(data,'sourceGroups');
  if(hasGroups){if(!Array.isArray(data.sourceGroups)||!data.sourceGroups.length||data.sourceGroups.length>8||new Set(data.sourceGroups).size!==data.sourceGroups.length)malformed();for(const group of data.sourceGroups)id(group);}
  if(o.kind==='key')key(data);
  else if(o.kind==='selection'){shape(data,['selection','backward']);range(data.selection,o.before.value);if(typeof data.backward!=='boolean')malformed();}
  else if(o.kind==='text'){shape(data,['inputType','text','replacement',...(hasGroups?['sourceGroups']:[])]);text(data.inputType,64);if(!data.inputType)malformed();text(data.text);range(data.replacement,o.before.value);}
  else if(o.kind==='composition'){
    const begin=data.operation==='begin';shape(data,['operation','text','selection',...(begin?['replacement']:[]),...(begin&&hasGroups?['sourceGroups']:[])]);
    if(!['begin','update','commit','cancel'].includes(data.operation))malformed();text(data.text);range(data.selection,data.text);if(begin)range(data.replacement,o.before.value);
    if(data.operation==='cancel'&&(data.text!==''||!same(data.selection,[0,0])))malformed();
  }else malformed();
};
const revocation = value => {shape(value,['reason','basis','composition','keys','incarnation']);text(value.reason,512);basis(value.basis);nullable(value.composition);id(value.incarnation);if(!Array.isArray(value.keys)||value.keys.length>64)malformed();for(const held of value.keys)key(held,true);};
const signature = (snapshot,surface) => JSON.stringify(canonical([snapshot.revision,surface]));
const logical = value => value===null||value.state==='ended'?null:value.transaction;
const pendingEditor = (snapshot,surface) => !snapshot.closed&&surface?.presentation?.available&&surface.presentation.editor?.editable&&surface.focused&&surface.active&&!surface.serviceActive&&(BigInt(surface.capabilities.supported)&63n)===63n;
const joinedReceipt = (publication,value) => {
  if(value.outcome==='unknown')return;
  if(!publication||!same(publication.settlement,{session:value.session,id:value.id,predecessor:value.predecessor,submittedToken:value.submittedToken})||
      !same(nativeBasis(publication.basis),nativeBasis(value.basis))||!same(publication.composition,value.composition)||!same(publication.retirement,value.retirement))throw Error('Editor receipt has no accepted paired publication');
};

export function validateEditorPublication(snapshot,surface,value){
  validateSurfaceState(snapshot,surface,'editor_v1');const copy=owned(value);if(copy===null)return copy;
  shape(copy,['basis','settlement','composition','retirement']);if(copy.basis!==null)basis(copy.basis);if(copy.settlement!==null)tag(copy.settlement);composition(copy.composition);retirement(copy.retirement);
  if(copy.basis!==null){
    const p=surface?.presentation,e=p?.editor,b=copy.basis;
    if(copy.retirement!==null||!p||!e||!same(b.identity,p.identity)||b.editorRevision!==e.revision||b.surrounding!==e.surrounding||!same(b.selection,e.selection)||b.backward!==e.selectionBackward||b.composition!==e.compositionTransaction||logical(copy.composition)!==surface.composition)malformed();
  }else if(copy.composition!==null&&(copy.composition.state!=='ended'||copy.retirement===null||(surface!==null&&surface.composition!==null)))malformed();
  return copy;
}

export function validateEditorOperation(value,snapshot,surface,publication){
  const copy=owned(value);
  publication=validateEditorPublication(snapshot,surface,publication);
  if(!snapshot||snapshot.closed)stale();
  if(copy?.type==='editorSubmit'){
    shape(copy,['type','packet']);packet(copy.packet);
    if(!publication?.basis||!same(nativeBasis(copy.packet.basis),nativeBasis(publication.basis))||!surface?.presentation?.available||!surface.presentation.editor?.editable||!surface.focused||!surface.active||surface.serviceActive)stale();
  }else if(copy?.type==='editorRevoke'){shape(copy,['type','record']);revocation(copy.record);}
  else if(copy?.type==='editorTake'){shape(copy,['type','ticket']);id(copy.ticket);}
  else if(copy?.type==='editorResync')shape(copy,['type']);
  else malformed();
  validateSurfaceState(snapshot,surface,'editor_v1');return copy;
}

export function validateEditorReply(value,operation=null,sequence=null){
  const copy=owned(value);if(copy===null)malformed();id(copy.sequence);
  if(sequence!==null&&copy.sequence!==sequence)throw Error('Editor reply sequence differs');
  if(operation!==null&&copy.type!==operation.type)throw Error('Editor reply type differs');
  if(copy.type==='editorSubmit'||copy.type==='editorRevoke'){shape(copy,['type','sequence','ticket']);nullable(copy.ticket);}
  else if(copy.type==='editorResync')shape(copy,['type','sequence']);
  else if(copy.type==='editorTake'){
    shape(copy,['type','sequence','ticket','completion']);id(copy.ticket);if(operation!==null&&copy.ticket!==operation.ticket)throw Error('Editor reply ticket differs');
    if(copy.completion!==null){const c=copy.completion;shape(c,['ticket','admission','receipt','detail']);if(c.ticket!==copy.ticket||!['completed','rejected','busy','unavailable','terminal','awaiting_projection','prepared'].includes(c.admission))malformed();text(c.detail,4096);if(c.receipt!==null)receipt(c.receipt);}
  }else malformed();return copy;
}

// The endpoint owns transport correlation and accepted metadata only. The one
// existing controller and native owner retain all editing/application policy.
export function createBrowserEditorEndpoint({send,scheduler=globalThis,maxPolls=64,pollInterval=0,onFailure=()=>{}}={}){
  if(typeof send!=='function'||typeof onFailure!=='function'||!Number.isSafeInteger(maxPolls)||maxPolls<1||maxPolls>128||!Number.isSafeInteger(pollInterval)||pollInterval<0||pollInterval>1000)malformed();
  let closed=false,current=null,lastSequence=0n;const paired=new Map(),timers=new Map();
  const fail=error=>{close(error);try{onFailure(error);}catch{}return null;};
  const close=(error=Error('Editor endpoint closed'))=>{if(closed)return;closed=true;current=null;paired.clear();for(const [timer,reject]of timers){scheduler.clearTimeout(timer);reject(error);}timers.clear();};
  const wait=()=>new Promise((resolve,reject)=>{if(closed){reject(Error('Editor endpoint closed'));return;}let timer;timer=scheduler.setTimeout(()=>{timers.delete(timer);resolve();},pollInterval);timers.set(timer,reject);});
  const exchange=async operation=>{
    if(closed)throw Error('Editor endpoint closed');
    if(!current)throw Error('Editor endpoint has no accepted state');
    const request=validateEditorOperation(operation,current.snapshot,current.surface,current.publication);
    const reply=validateEditorReply(await send(request),request);
    if(closed)throw Error('Editor endpoint closed');
    const accepted=paired.get(reply.sequence);
    if(!accepted||!same(accepted,reply)||BigInt(reply.sequence)<=lastSequence)throw Error('Editor reply was not accepted with its paired state');
    paired.delete(reply.sequence);lastSequence=BigInt(reply.sequence);return reply;
  };
  const run=async operation=>{
    const queued=await exchange(operation);if(queued.ticket===null)throw Error('Editor request was not admitted');
    for(let n=0;n<maxPolls;++n){
      const reply=await exchange({type:'editorTake',ticket:queued.ticket});
      if(reply.completion!==null){
        if(reply.completion.receipt!==null){
          const r=reply.completion.receipt,p=operation.packet;
          if(p&&(!same([r.session,r.id,r.predecessor,r.submittedToken],[p.session,p.observation.id,p.observation.predecessor,p.basis.token])))throw Error('Editor completion head differs');
          if(p&&r.basis===null&&r.outcome!=='unknown')copyEditorRetirement(r.retirement,p.basis.identity);
          return r;
        }
        if(operation.type==='editorRevoke'&&reply.completion.admission==='completed')return reply.completion;
        throw Error('Editor completion has no checked receipt: '+reply.completion.admission);
      }
      if(n+1<maxPolls)await wait();
    }
    throw Error('Editor completion polling budget exhausted');
  };
  return Object.freeze({
    accept(snapshot,surface,publication,reply=null){
      if(closed)return;
      const captured=validateEditorPublication(snapshot,surface,publication);
      if(reply!==null){const checked=validateEditorReply(reply);if(checked.type==='editorTake'&&checked.completion?.receipt)joinedReceipt(captured,checked.completion.receipt);
        if(BigInt(checked.sequence)>lastSequence){if(paired.has(checked.sequence)&&!same(paired.get(checked.sequence),checked))throw Error('Editor reply changed after publication');if(!paired.has(checked.sequence)&&paired.size>=128)throw Error('Editor paired reply queue is full');paired.set(checked.sequence,checked);}}
      const owner=surface?.presentation?.identity.owner;
      const widgets=owner?snapshot.widgets.filter(w=>w.key.id===owner.id&&w.key.generation===owner.generation).map(w=>({key:w.key,visible:w.visible,enabled:w.enabled,inModal:w.inModal,bounds:w.bounds,clip:w.clip})):[];
      current={snapshot:owned({revision:snapshot.revision,closed:snapshot.closed,scale:snapshot.scale,widgets}),surface:owned(surface),publication:captured,signature:signature(snapshot,surface)};
    },
    resolveBasis(snapshot,surface){if(closed||!current||signature(snapshot,surface)!==current.signature)return null;validateSurfaceState(snapshot,surface,'editor_v1');const p=current.publication;if(p===null)return pendingEditor(snapshot,surface)?Object.freeze({pending:true}):null;return p.basis!==null?Object.freeze({basis:p.basis,settlement:p.settlement}):p.retirement===null?null:Object.freeze({basis:null,settlement:p.settlement,retirement:p.retirement});},
    sendObservation(value){return run({type:'editorSubmit',packet:owned(value)}).catch(error=>{fail(error);throw error;});},
    revoke(value){const result=run({type:'editorRevoke',record:owned(value)});result.catch(fail);return result;},
    resync(){const result=exchange({type:'editorResync'});result.catch(fail);return result;},
    close
  });
}
