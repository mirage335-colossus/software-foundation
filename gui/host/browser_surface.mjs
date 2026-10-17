import {validateSurfaceState} from './browser_surface_protocol.mjs';
// Generic physical input for the optional surface companion. No page content,
// engine object, transport envelope or service capability belongs in this module.
export const BASIC_SURFACE_FEATURES = 97n; // raw_keys | focus | raw_pointer
const maximum = 18446744073709551615n;
const sameOwner = (a,b) => a?.id === b?.id && a?.generation === b?.generation;
const contextKey = identity => JSON.stringify([identity.owner,identity.generation,identity.epoch,identity.context]);
const scalarText = value => {
  if (typeof value !== 'string' || value.includes('\0')) return false;
  for (const character of value) { const point=character.codePointAt(0); if (point>=0xd800 && point<=0xdfff) return false; }
  return true;
};
const modifiers = event => (event.shiftKey?1:0)|(event.ctrlKey?2:0)|(event.altKey?4:0)|(event.metaKey?8:0)|(event.getModifierState?.('AltGraph')?16:0);
const keyId = input => JSON.stringify([input.code || input.key,input.location]);
export function captureSurfaceKey(policy,input) {
  for (const rule of policy.rules) if ((input.phase === 'down' ? rule.down : rule.up) &&
      (!rule.key || rule.key === input.key) && (!rule.code || rule.code === input.code) &&
      (input.modifiers & rule.requiredModifiers) === rule.requiredModifiers && !(input.modifiers & rule.forbiddenModifiers)) return rule.disposition;
  return policy.fallback;
}
// Exact scalar boundaries, intentionally unlike the legacy permissive helpers.
// Editor companions use this same scalar boundary conversion.
export function surfaceScalarMap(text) {
  if (!scalarText(text)) throw Error('Invalid surface text');
  const utf16ToBytes=new Map([[0,0]]),bytesToUtf16=new Map([[0,0]]),encoder=new TextEncoder();
  let bytes=0,utf16=0;
  for (const character of text) { bytes+=encoder.encode(character).length; utf16+=character.length; utf16ToBytes.set(utf16,bytes); bytesToUtf16.set(bytes,utf16); }
  const at=(map,index)=>{if(!Number.isSafeInteger(index)||!map.has(index))throw Error('Invalid surface text boundary');return map.get(index);};
  return Object.freeze({byteOffset:index=>at(utf16ToBytes,index),utf16Offset:index=>at(bytesToUtf16,index)});
}

export function createBrowserSurface({root,document=globalThis.document,send,resolveOwner,onFailure=()=>{},profile='legacy',classifyContext,editor}) {
  if (!root || !document || typeof send !== 'function' || typeof resolveOwner !== 'function') throw Error('Surface requires a root, document, sender and owner resolver');
  if(!['legacy','mouse_v1','editor_v1'].includes(profile)||(classifyContext!==undefined&&typeof classifyContext!=='function'))throw Error('Invalid surface profile');
  const editorProfile=profile==='editor_v1';
  if(editorProfile&&(!editor||!['createBridge','resolveBasis','sendObservation','revoke','resync'].every(key=>typeof editor[key]==='function')||(editor.trace!==undefined&&typeof editor.trace!=='function')))throw Error('Editor surface requires an authoritative endpoint');
  const mouseProfile=profile!=='legacy',allowedFeatures=editorProfile?8255n:mouseProfile?8225n:BASIC_SURFACE_FEATURES,buttonBits=[1,4,2,8,16];
  const host=document.defaultView || globalThis,listeners=[],held=new Map(),bodyHeld=new Map(),pointers=new Map();
  let closed=false,connecting=false,connected=false,connection=null,accepted=null,snapshot=null,service=false,sequence=0n,pointerSerial=0n,focusPending=null;
  let mouse=null,nativeLease=null,releasingMouse=null,editorBridge=null;
  const focusQueue=[];
  let installed=0n;
  const listen=(target,type,callback,options)=>{if(typeof target?.addEventListener!=='function')return false;target.addEventListener(type,callback,options);listeners.push([target,type,callback,options]);return true;};
  const features=()=>connected&&!closed?installed&BigInt(accepted?.capabilities?.supported||'0'):0n;
  const live=()=>!closed&&connected&&!service&&accepted?.presentation?.available&&!snapshot?.closed;
  const owner=(event,basis=accepted)=>basis?.presentation ? resolveOwner({...basis.presentation.identity.owner},event) : null;
  const focused=(basis=accepted)=>{if(editorBridge?.focused(basis?.presentation?.identity))return true;const node=owner(undefined,basis);return !!node&&(document.activeElement===node||node.contains?.(document.activeElement));};
  const report=error=>{if(!closed)onFailure(error);};
  const post=(input,basis=accepted)=>{
    if(!live())return Promise.resolve(false);
    if(sequence===maximum){report(Error('Surface input sequence exhausted'));close();return Promise.resolve(false);}
    const operation={type:'surfaceInput',identity:structuredClone(basis.presentation.identity),sequence:String(++sequence),input};
    // An event retains the presentation that produced it. Never rebase/replay it.
    let result;try{result=send(operation);}catch(error){report(error);return Promise.resolve(false);}
    return Promise.resolve(result).then(()=>!closed,error=>{if(!closed)report(error);return false;});
  };
  const drainFocus=()=>{
    if(focusPending||!focusQueue.length||!live())return;
    const record=focusQueue.shift();focusPending=record;
    post(record.input,record.basis).finally(()=>{focusPending=null;if(!closed)drainFocus();});
  };
  const focusInput=(cause='direct',active=true)=>{
    if(!live()||(!mouseProfile&&!(features()&32n)))return;
    const basis=accepted,value=focused(basis);
    if(!(features()&32n)){
      // Mouse capture must retire on native loss even when focus delivery was
      // not negotiated. This is cancellation, never an invented focus record.
      if(mouseProfile&&(!value||!active)){held.clear();bodyHeld.clear();cancelMouse(true,basis);}
      return;
    }
    // Native loss retires local interaction immediately, even while an earlier
    // focus receipt is pending. Keep loss as an ordering barrier in the queue.
    if(!value||!active){held.clear();bodyHeld.clear();cancelPointers(false);}
    if(!focusPending&&!focusQueue.length&&basis.focused===value&&basis.active===active)return;
    const input={kind:'focus',focused:value,active,cause},last=focusQueue.at(-1)||focusPending;
    if(last&&JSON.stringify([last.basis.presentation.identity,last.input])===JSON.stringify([basis.presentation.identity,input]))return;
    if(focusQueue.length>=64){report(Error('Surface focus queue is full'));close();return;}
    focusQueue.push({input,basis});drainFocus();
  };
  const keyboard=event=>{
    // Textarea incarnations never fall through into the physical body lane.
    if(editorProfile&&event.isTrusted!==true)return;
    const ingress=editorProfile?accepted:null;
    if(!live()||!(features()&1n)||!focused()||event.defaultPrevented)return;
    const basis=accepted; if(editorProfile&&basis!==ingress)return;
    const input={kind:'key',phase:event.type==='keyup'?'up':'down',key:event.key,code:event.code||'',location:event.location||0,modifiers:modifiers(event),repeat:!!event.repeat};
    if(!scalarText(input.key)||!input.key||new TextEncoder().encode(input.key).length>64||!/^[\x21-\x7e]*$/.test(input.code)||input.code.length>64||!Number.isInteger(input.location)||input.location<0||input.location>3)return;
    const id=keyId(input),keys=editorProfile?bodyHeld:held; let bodyEntry=null;
    if(editorProfile){
      const previous=bodyHeld.get(id); bodyEntry=previous;
      const original=previous?.identity,current=basis.presentation.identity;
      const release=input.phase==='up'&&previous&&previous.input.location===input.location&&
        ((previous.input.code&&input.code)?previous.input.code===input.code:
          previous.input.code===input.code&&previous.input.key===input.key)&&sameOwner(original.owner,current.owner)&&
        ['generation','epoch','context'].every(key=>original[key]===current[key]);
      const bridgeTarget=editorBridge.ownsTarget(event.target);
      if(bridgeTarget){
        if(!release||event.target!==document.activeElement||!root.contains?.(event.target)||!editorBridge.focused(current))return;
      }else{
        const target=owner(event,basis);
        if(!target||!(event.target===target||target.contains?.(event.target)))return;
      }
      if(accepted!==basis||!live())return;
      // Only a real matching release may cross a pending/editor admission
      // fence. The App still joins the actual consumed down's full engine
      // target and native core; this copied public identity proves neither.
      if(input.phase==='up'?!release:(basis.presentation.editor||!editorBridge.allowsBodyKey(current)))return;
      if(input.phase==='up'&&!previous.submitted){bodyHeld.delete(id);return;}
    }
    if(input.phase==='up'){if(!keys.has(id))return;input.repeat=false;keys.delete(id);}
    else if(input.repeat){if(!keys.has(id)||(editorProfile&&!bodyEntry.submitted))return;}
    else {if(keys.has(id)||keys.size>=64)return;
      if(editorProfile)bodyEntry={input:Object.freeze({key:input.key,code:input.code,location:input.location}),
        identity:structuredClone(basis.presentation.identity),submitted:false};
      keys.set(id,editorProfile?bodyEntry:input);}
    if(captureSurfaceKey(basis.presentation.keys,input)==='capture')event.preventDefault();
    // An alias uses the accepted presentation revision while retaining exact
    // original body context; no queued observation or native target is rebased.
    event.stopImmediatePropagation?.();focusInput();
    if(editorProfile){
      if(accepted!==basis||!live()||!(features()&1n)){
        if(input.phase==='down'&&keys.get(id)===bodyEntry&&!bodyEntry.submitted)keys.delete(id);
        return;
      }
      if(input.phase==='down'){if(keys.get(id)!==bodyEntry)return;bodyEntry.submitted=true;}
      else if(keys.has(id))return;
    }
    post(input,basis);
  };
  const point=(event,basis)=>{const box=root.getBoundingClientRect();const bounds=basis.presentation.bounds;return {x:event.clientX-box.left-bounds[0],y:event.clientY-box.top-bounds[1],absoluteX:event.clientX-box.left,absoluteY:event.clientY-box.top};};
  const inside=(p,clip)=>p.absoluteX>=clip[0]&&p.absoluteY>=clip[1]&&p.absoluteX<clip[0]+clip[2]&&p.absoluteY<clip[1]+clip[3];
  const stop=event=>{event.preventDefault?.();event.stopImmediatePropagation?.();};
  const release=(id,entry)=>{pointers.delete(id);try{root.releasePointerCapture(id);}catch{}};
  const mouseValue=(phase,entry,values={})=>({kind:'mouse',version:1,phase,captureToken:entry?.token||'0',x:0,y:0,wheelX:0,wheelY:0,button:0,buttons:entry?.buttons||0,clicks:0,modifiers:0,contextOrigin:'pointer',...values});
  const releaseMouse=entry=>{
    if(mouse===entry)mouse=null;
    if(nativeLease!==entry)return;
    nativeLease=null;
    const previous=releasingMouse;releasingMouse=entry;
    try{root.releasePointerCapture(entry.nativeId);}catch{}finally{releasingMouse=previous;}
  };
  const cancelMouse=(notify=true,basis=accepted,entry=mouse)=>{
    if(!entry||mouse!==entry)return;
    // Keep entry.lastPoint intact: canonical cancellation has no new real point.
    mouse=null;
    if(notify&&live()&&(features()&8192n))post(mouseValue('cancel',entry,{buttons:0}),basis);
    // send and native release can each install a successor with this DOM ID.
    releaseMouse(entry);
  };
  const cancelPointers=(notify=true)=>{
    if(mouseProfile){cancelMouse(notify);return;}
    const basis=accepted;
    for(const [id,entry] of [...pointers]){release(id,entry);if(notify&&live())post({kind:'pointer',phase:'cancel',pointer:entry.token,x:0,y:0,wheelX:0,wheelY:0,button:0,buttons:0,clicks:1,modifiers:0},basis);}
  };
  const pointer=event=>{
    if(!live()||!(features()&64n))return;
    const phase={pointerdown:'down',pointerup:'up',pointercancel:'cancel',lostpointercapture:'cancel',pointermove:'move',wheel:'wheel',contextmenu:'context'}[event.type];
    if(!phase)return;
    const basis=accepted;
    let entry=pointers.get(event.pointerId),p=point(event,basis);
    if(!entry&&(!owner(event,basis)||!inside(p,basis.presentation.clip)))return;
    if(![p.x,p.y].every(value=>Number.isFinite(value)&&Math.abs(value)<=1000000))return;
    const button=phase==='wheel'||phase==='context'||phase==='cancel'?0:(event.button<0?0:event.button||0),buttons=phase==='cancel'?0:event.buttons||0;
    if(!Number.isInteger(button)||button<0||button>4||!Number.isInteger(buttons)||buttons<0||buttons>31)return;
    if(phase==='down'){
      if(entry||pointers.size>=64||pointerSerial===maximum||!Number.isInteger(event.pointerId))return;
      stop(event); // This accepted route stays owned if a callback retires it.
      // Native iframe focus may report a transient loss before activeElement
      // changes. Finish that transition before installing a new pointer owner.
      owner(undefined,basis)?.focus?.({preventScroll:true});focusInput();
      const current=()=>live()&&(features()&64n)&&JSON.stringify(accepted?.presentation?.identity)===JSON.stringify(basis.presentation.identity)&&owner(event,basis);
      if(!current()||pointers.has(event.pointerId)||pointers.size>=64||pointerSerial===maximum)return;
      entry={token:String(++pointerSerial),context:contextKey(basis.presentation.identity)};pointers.set(event.pointerId,entry);
      try{root.setPointerCapture(event.pointerId);}catch{if(pointers.get(event.pointerId)===entry)pointers.delete(event.pointerId);return;}
      // Both focus and native capture are callback boundaries. A retired token
      // must never resume this outer press or acquire a successor's identity.
      if(!current()||pointers.get(event.pointerId)!==entry){if(pointers.get(event.pointerId)===entry)release(event.pointerId,entry);return;}
    } else if(['up','cancel'].includes(phase)) {if(!entry)return;release(event.pointerId,entry);}
    if(phase==='context'&&pointers.size)return;
    let wheelX=0,wheelY=0;
    if(phase==='wheel'){
      const mode=event.deltaMode||0;if(![0,1,2].includes(mode))return;
      const factor=mode===1?16:mode===2?Math.max(1,basis.presentation.bounds[3]):1;
      wheelX=event.deltaX*factor;wheelY=event.deltaY*factor;
      if(![wheelX,wheelY].every(value=>Number.isFinite(value)&&Math.abs(value)<=1000000)||(!wheelX&&!wheelY))return;
    }
    if(phase!=='down')stop(event);
    post({kind:'pointer',phase,pointer:entry?.token||'0',x:p.x,y:p.y,wheelX,wheelY,button,buttons,clicks:Number.isInteger(event.detail)?Math.max(1,Math.min(3,event.detail)):1,modifiers:modifiers(event)},basis);
  };
  const mouseCurrent=basis=>live()&&accepted.active&&(features()&8192n)&&JSON.stringify(accepted?.presentation?.identity)===JSON.stringify(basis.presentation.identity);
  const mousePoint=(event,basis)=>{
    const p=point(event,basis);return [p.x,p.y].every(value=>Number.isFinite(value)&&Math.abs(value)<=1000000)?p:null;
  };
  const mouseIntent=event=>{
    if(!live()||!accepted.active||!(features()&8192n)||event.isTrusted!==true)return;
    const basis=accepted,entry=mouse;
    if(event.type==='contextmenu'){
      const node=owner(undefined,basis),p=mousePoint(event,basis);
      const ownedTarget=node&&(event.target===node||node.contains?.(event.target));
      if(!ownedTarget&&!(entry&&event.pointerId===entry.nativeId)&&!(p&&owner(event,basis)&&inside(p,basis.presentation.clip)))return;
      stop(event);
      if(event.pointerType&&event.pointerType!=='mouse')return;
      let origin;try{origin=classifyContext(event);}catch{return;}
      if(!['pointer','keyboard'].includes(origin)||(event.pointerType==='mouse'&&origin!=='pointer')||!mouseCurrent(basis)||mouse!==entry)return;
      if(origin==='keyboard'){
        if(!focused(basis))return;
        post(mouseValue('context',entry,{contextOrigin:'keyboard'}),basis);return;
      }
      if(!p||!owner(event,basis)||!inside(p,basis.presentation.clip))return;
      if(entry&&event.pointerId!==undefined&&event.pointerId!==entry.nativeId)return;
      if(!Number.isInteger(event.buttons)||event.buttons!==(entry?.buttons||0))return;
      if(entry)entry.lastPoint={x:p.x,y:p.y};
      post(mouseValue('context',entry,{x:p.x,y:p.y,modifiers:modifiers(event)}),basis);return;
    }
    if(event.type==='wheel'){
      const p=mousePoint(event,basis),mode=event.deltaMode;
      if(!p||!owner(event,basis)||!inside(p,basis.presentation.clip)||![0,1,2].includes(mode))return;
      const factor=mode===1?16:mode===2?Math.max(1,basis.presentation.bounds[3]):1;
      const scaled=[event.deltaX*factor,event.deltaY*factor];
      if(!scaled.every(value=>Number.isFinite(value)&&Math.abs(value)<=1000000))return;
      const [wheelX,wheelY]=scaled.map(value=>Math.fround(value)||0);
      if(!wheelX&&!wheelY)return;
      stop(event);if(entry)entry.lastPoint={x:p.x,y:p.y};
      post(mouseValue('wheel',entry,{x:p.x,y:p.y,wheelX,wheelY,modifiers:modifiers(event)}),basis);return;
    }
    if(['pointercancel','lostpointercapture'].includes(event.type)){
      if(event.type==='lostpointercapture'&&releasingMouse?.nativeId===event.pointerId)return;
      if(entry&&event.pointerId===entry.nativeId){stop(event);cancelMouse(true,basis,entry);}return;
    }
    if(!['pointerdown','pointerup','pointermove'].includes(event.type)||event.pointerType!=='mouse'||!Number.isSafeInteger(event.pointerId)||event.pointerId<0)return;
    const p=mousePoint(event,basis);
    if(!entry&&(!p||!owner(event,basis)||!inside(p,basis.presentation.clip)))return;
    if(entry&&event.pointerId!==entry.nativeId){stop(event);cancelMouse(true,basis,entry);return;}
    const after=event.buttons,button=event.button;
    if(!p||!Number.isInteger(after)||after<0||after>31||!Number.isInteger(button)||button< -1||button>4){if(entry){stop(event);cancelMouse(true,basis,entry);}return;}
    const before=entry?.buttons||0,changed=before^after;
    let phase='move';
    if(changed){
      if((changed&(changed-1))||button<0||buttonBits[button]!==changed||(event.type==='pointerdown'&&!(after&changed))||(event.type==='pointerup'&&(after&changed))){if(entry){stop(event);cancelMouse(true,basis,entry);}return;}
      phase=after&changed?'down':'up';
    }else if(button!==-1||event.type!=='pointermove'){if(entry){stop(event);cancelMouse(true,basis,entry);}return;}
    if(!entry&&((phase!=='move'&&event.type!=='pointerdown')||phase==='up'||(phase==='move'&&after)))return;
    stop(event);
    let currentEntry=entry;
    if(!entry&&phase==='down'){
      if(pointerSerial===maximum)return;
      owner(undefined,basis)?.focus?.({preventScroll:true});focusInput();
      if(!mouseCurrent(basis)||mouse||!owner(event,basis)||!inside(p,basis.presentation.clip)||pointerSerial===maximum)return;
      currentEntry={nativeId:event.pointerId,token:String(++pointerSerial),buttons:after,lastPoint:{x:p.x,y:p.y},context:contextKey(basis.presentation.identity)};
      mouse=currentEntry;nativeLease=currentEntry;
      try{root.setPointerCapture(event.pointerId);}catch{if(mouse===currentEntry)mouse=null;if(nativeLease===currentEntry)nativeLease=null;return;}
      if(!mouseCurrent(basis)||mouse!==currentEntry){releaseMouse(currentEntry);return;}
    }else if(entry){entry.buttons=after;entry.lastPoint={x:p.x,y:p.y};}
    const terminal=phase==='up'&&!after;
    if(terminal)mouse=null;
    post(mouseValue(phase,currentEntry,{x:p.x,y:p.y,button:phase==='move'?0:button,buttons:after,modifiers:modifiers(event)}),basis);
    if(terminal)releaseMouse(currentEntry);
  };
  const externalBlur=()=>{editorBridge?.retire('Native surface lost focus');focusInput('external',false);};
  const visibility=()=>{if(document.visibilityState==='hidden')externalBlur();else focusInput('external',true);};
  const close=()=>{
    if(closed)return;closed=true;connected=false;connecting=false;accepted=null;snapshot=null;held.clear();bodyHeld.clear();focusQueue.length=0;cancelPointers(false);
    editorBridge?.close();
    for(const [target,type,callback,options] of listeners)target.removeEventListener(type,callback,options);listeners.length=0;
  };
  if(editorProfile){
    editorBridge=editor.createBridge({root,document,onFailure:error=>{close();onFailure(error);}});
    if(!editorBridge||!['accept','focused','allowsBodyKey','ownsTarget','retire','close'].every(key=>typeof editorBridge[key]==='function'))throw Error('Invalid editor bridge');
    installed|=30n;
  }
  if(listen(document,'keydown',keyboard,{capture:true})&&listen(document,'keyup',keyboard,{capture:true}))installed|=1n;
  if(typeof root.focus==='function'&&listen(document,'focusin',()=>focusInput(),{capture:true})&&listen(document,'focusout',event=>{
    // Native focus algorithms may expose an intermediate activeElement while
    // transferring to our own textarea. That transfer does not blur the native
    // surface or retire a held body release; it grants no new key admission.
    if(editorProfile&&event.relatedTarget&&root.contains?.(event.relatedTarget)&&editorBridge.ownsTarget(event.relatedTarget))return;
    focusInput('external');
  },{capture:true}))installed|=32n;
  if(typeof root.setPointerCapture==='function'&&typeof root.releasePointerCapture==='function'&&typeof root.getBoundingClientRect==='function'&&typeof host.PointerEvent==='function'){
    if(!mouseProfile||typeof classifyContext==='function'){
      for(const type of ['pointerdown','pointerup','pointercancel','lostpointercapture','pointermove','wheel','contextmenu'])listen(root,type,mouseProfile?mouseIntent:pointer,{capture:true,passive:false});
      installed|=mouseProfile?8192n:64n;
    }
  }
  for(const type of mouseProfile?['click','dblclick','auxclick']:['click','dblclick'])listen(root,type,event=>{
    if(!live())return;
    const node=owner(),ownedTarget=node&&(event.target===node||node.contains?.(event.target));
    // Keyboard activation has no meaningful pointer coordinates, and remains
    // owned when raw keys are negotiated without raw pointer support.
    if(((features()&(mouseProfile?8192n:64n))&&owner(event))||((features()&1n)&&event.detail===0&&ownedTarget))stop(event);
  },{capture:true});
  listen(host,'blur',externalBlur);listen(host,'focus',()=>focusInput('external',true));listen(host,'pagehide',close,{once:true});listen(document,'visibilitychange',visibility);
  const api={
    capabilities:features,
    owns:key=>!!live()&&sameOwner(key,accepted.presentation.identity.owner),
    connect(){
      if(closed)return Promise.reject(Error('Surface is closed'));
      if(connection)return connection;
      connecting=true;
      const offer=editorProfile?{type:'surfaceConnect',version:2,profile:'editor_v1',supported:String(installed)}:{type:'surfaceConnect',version:1,supported:String(installed)};
      if(installed&8192n)offer.mouseInputVersion=1;
      let result;try{result=send(offer);}catch(error){connecting=false;report(error);close();connection=Promise.resolve(false);return connection;}
      connection=Promise.resolve(result).then(()=>{if(closed)return false;if(!accepted||BigInt(accepted.capabilities.supported)&~installed)throw Error('Invalid surface capability acceptance');connected=true;connecting=false;editorBridge?.accept(snapshot,accepted,{serviceActive:service,connected});if(closed)return false;focusInput();return true;}).catch(error=>{connecting=false;if(!closed)report(error);close();return false;});
      return connection;
    },
    accept(nextSnapshot,nextSurface,{serviceActive=false}={}){
      if(closed)return;
      validateSurfaceState(nextSnapshot,nextSurface,profile);
      const previous=accepted?.presentation;
      if(nextSurface?.presentation){
        const p=nextSurface.presentation,w=nextSnapshot.widgets?.find(value=>sameOwner(value.key,p.identity.owner));
        if(p.identity.presentationRevision!==nextSnapshot.revision||!w||(p.available&&(!w.visible||!w.enabled||!w.inModal))||(!editorProfile&&p.editor)||p.clipboard||p.popup||BigInt(nextSurface.capabilities.supported)&~allowedFeatures)throw Error('Invalid accepted browser surface');
      }
      const ownedSurface=nextSurface===null?null:structuredClone(nextSurface);
      snapshot=editorProfile?structuredClone(nextSnapshot):{closed:nextSnapshot.closed,revision:nextSnapshot.revision};accepted=ownedSurface;service=!!serviceActive||!!nextSurface?.serviceActive;
      if(nextSurface?.lastSequence!==undefined){const last=BigInt(nextSurface.lastSequence);if(last>sequence)sequence=last;}
      const next=accepted?.presentation;
      if(editorProfile&&(!next||!previous||!sameOwner(next.identity.owner,previous.identity.owner)||
          ['generation','epoch','context'].some(key=>next.identity[key]!==previous.identity[key])||service||nextSnapshot.closed||
          !next.available||!nextSurface.active||!(BigInt(nextSurface.capabilities.supported)&1n)))bodyHeld.clear();
      if(!next||!previous||contextKey(next.identity)!==contextKey(previous.identity)||service||nextSnapshot.closed||(mouseProfile&&(!next.available||!nextSurface.active||!(BigInt(nextSurface.capabilities.supported)&8192n)))){held.clear();focusQueue.length=0;cancelPointers(false);}
      else if(JSON.stringify([next.bounds,next.clip])!==JSON.stringify([previous.bounds,previous.clip]))cancelPointers(true);
      if(nextSnapshot.closed)close();
      else editorBridge?.accept(snapshot,accepted,{serviceActive:service,connected});
    },
    cancelPointers:()=>cancelPointers(true),close
  };
  return Object.freeze(api);
}
