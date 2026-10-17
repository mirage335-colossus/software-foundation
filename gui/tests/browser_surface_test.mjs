import assert from 'node:assert/strict';
import {createBrowserSurface,surfaceScalarMap,captureSurfaceKey} from '../host/browser_surface.mjs';
import {validateSurfaceOperation} from '../host/browser_surface_protocol.mjs';
class Target{
  constructor(){this.events=new Map();}
  addEventListener(type,fn){if(!this.events.has(type))this.events.set(type,new Set());this.events.get(type).add(fn);}
  removeEventListener(type,fn){this.events.get(type)?.delete(fn);}
  emit(type,values={}){const event={type,prevented:false,stopped:false,preventDefault(){this.prevented=true;},stopImmediatePropagation(){this.stopped=true;},...values};for(const fn of [...(this.events.get(type)||[])]){fn(event);if(event.stopped)break;}return event;}
}
function fixture(options={}){
  const host=new Target();host.PointerEvent=class{};
  const document=new Target();document.defaultView=host;document.visibilityState='visible';
  const root=new Target();root.contains=value=>value===root;root.getBoundingClientRect=()=>({left:10,top:20});root.captured=new Set();
  root.focus=()=>{document.activeElement=root;document.emit('focusin');};
  root.setPointerCapture=id=>root.captured.add(id);root.releasePointerCapture=id=>{root.captured.delete(id);root.emit('lostpointercapture',{pointerId:id,clientX:10,clientY:20,isTrusted:options.profile==='mouse_v1'});};
  const operations=[],errors=[];let acknowledge,onSend=null;
  const surface=createBrowserSurface({root,document,resolveOwner:(key,event)=>key.id==='surface'&&!event?.blocked?root:null,
    send:operation=>{operations.push(operation);onSend?.(operation);if(operation.type==='surfaceConnect')return new Promise(resolve=>{acknowledge=resolve;});return Promise.resolve({});},onFailure:error=>errors.push(error),...options});
  const snapshot={revision:'1',scale:1,closed:false,widgets:[{key:{id:'surface',generation:'1'},visible:true,enabled:true,inModal:true,bounds:[0,0,100,100],clip:[0,0,100,100]}]};
  const state={version:1,capabilities:{version:1,supported:'97',limits:{textBytes:65536,clipboardBytes:65536,popupItems:1024,popupTextBytes:65536,captureRules:64,heldKeys:64,popupDepth:8}},
    presentation:{identity:{owner:{id:'surface',generation:'1'},presentationRevision:'1',generation:'7',epoch:'1',context:'1'},required:'97',bounds:[0,0,100,100],clip:[0,0,100,100],displayScale:1,available:true,
      keys:{fallback:'pass',rules:[{key:'F5',code:'',requiredModifiers:0,forbiddenModifiers:0,down:true,up:true,disposition:'capture'}]},editor:null,clipboard:null,popup:null},focused:false,active:true,composition:null,lastSequence:'0',serviceActive:false};
  if(options.profile==='mouse_v1'){
    state.capabilities.supported=typeof options.classifyContext==='function'?'8225':'33';state.presentation.required=state.capabilities.supported;
    if(typeof options.classifyContext==='function')state.capabilities.mouseInputVersion=1;
  }
  return {host,document,root,surface,snapshot,state,operations,errors,setOnSend:value=>{onSend=value;},ack:()=>acknowledge({})};
}
const flush=async()=>{for(let i=0;i<4;i++)await Promise.resolve();};
async function connect(f){f.surface.accept(f.snapshot,f.state);const pending=f.surface.connect();assert.equal(f.surface.capabilities(),0n);f.ack();assert.equal(await pending,true);assert.equal(f.surface.capabilities(),BigInt(f.state.capabilities.supported));await flush();}
{
  const map=surfaceScalarMap('A😀éZ');assert.equal(map.byteOffset(3),5);assert.equal(map.utf16Offset(7),4);
  for(const index of [-1,2,2.5,99])assert.throws(()=>map.byteOffset(index));
  for(const index of [-1,2,3,4,6,99])assert.throws(()=>map.utf16Offset(index));
  for(const value of ['\ud800','\udc00','\0'])assert.throws(()=>surfaceScalarMap(value));
  assert.equal(captureSurfaceKey({fallback:'pass',rules:[{key:'x',code:'',requiredModifiers:16,forbiddenModifiers:2,down:true,up:false,disposition:'capture'}]},{phase:'down',key:'x',code:'KeyX',modifiers:16}),'capture');
}
{
  const f=fixture();assert.equal(f.surface.capabilities(),0n);assert.equal(f.operations.length,0);await connect(f);
  f.root.focus();await flush();assert.equal(f.operations.at(-1).input.kind,'focus');
  f.state={...f.state,focused:true,lastSequence:'1'};f.surface.accept(f.snapshot,f.state);await flush();
  const event=f.document.emit('keydown',{key:'F5',code:'F5',location:0,repeat:false});
  assert.equal(event.prevented,true,'Capture decision must precede backend completion');assert.equal(event.stopped,true);
  const operation=f.operations.at(-1);assert.equal(operation.input.kind,'key');assert.equal(operation.identity.presentationRevision,'1');
  const successor=structuredClone(f.state);successor.presentation.identity.presentationRevision='2';f.surface.accept({...f.snapshot,revision:'2'},successor);
  assert.equal(operation.identity.presentationRevision,'1','Queued input must never rebase');
  const up=f.document.emit('keyup',{key:'F5',code:'F5',location:0});assert.equal(up.prevented,true);assert.equal(f.operations.at(-1).identity.presentationRevision,'2');
  const pass=f.document.emit('keydown',{key:'a',code:'KeyA',location:0});assert.equal(pass.prevented,false,'Pass must permit native default');
  f.surface.close();assert.equal(f.surface.capabilities(),0n);const count=f.operations.length;f.document.emit('keydown',{key:'b',code:'KeyB'});assert.equal(f.operations.length,count);
}
{
  const f=fixture();await connect(f);const count=f.operations.length;
  f.root.emit('pointerdown',{pointerId:1,clientX:15,clientY:25,button:0,buttons:1,blocked:true});assert.equal(f.operations.length,count,'Interactive declaration above owner must block hit');
  f.root.emit('pointerdown',{pointerId:1,clientX:115,clientY:25,button:0,buttons:1});assert.equal(f.operations.length,count,'Outside clip must not capture');
  const event=f.root.emit('pointerdown',{pointerId:1,clientX:15,clientY:25,button:0,buttons:1});
  assert.equal(event.prevented,true);assert(f.root.captured.has(1));let operation=f.operations.at(-1);assert.equal(operation.input.phase,'down');assert.equal(operation.input.pointer,'1');assert.equal(operation.input.x,5);
  f.root.emit('pointermove',{pointerId:1,clientX:215,clientY:25,button:-1,buttons:1});operation=f.operations.at(-1);assert.equal(operation.input.phase,'move');assert.equal(operation.input.x,205,'Captured movement may leave clip');
  f.root.emit('pointerup',{pointerId:1,clientX:215,clientY:25,button:0,buttons:0});assert(!f.root.captured.has(1));assert.equal(f.operations.at(-1).input.phase,'up');
  f.root.emit('wheel',{clientX:15,clientY:25,deltaX:1,deltaY:-2,deltaMode:1});assert.equal(f.operations.at(-1).input.wheelY,-32);
  f.root.emit('contextmenu',{clientX:15,clientY:25});assert.equal(f.operations.at(-1).input.phase,'context');assert.equal(f.operations.at(-1).input.pointer,'0');
  f.root.emit('pointerdown',{pointerId:2,clientX:15,clientY:25,button:0,buttons:1});
  f.surface.accept(f.snapshot,{...f.state,serviceActive:true});assert.equal(f.root.captured.size,0,'Owned service must retire capture immediately');
  const stopped=f.operations.length;f.root.emit('pointermove',{pointerId:2,clientX:15,clientY:25,buttons:1});assert.equal(f.operations.length,stopped);
  f.surface.close();
}
{
  const f=fixture();f.surface.accept(f.snapshot,f.state);const pending=f.surface.connect();f.surface.close();f.ack();assert.equal(await pending,false);assert.equal(f.surface.capabilities(),0n,'Late connection cannot revive disposed adapter');
}
{
  const f=fixture();await connect(f);const next=structuredClone(f.state);next.presentation.identity.presentationRevision='2';assert.throws(()=>f.surface.accept(f.snapshot,next));
  const editor=structuredClone(f.state);editor.presentation.editor={surrounding:'private'};assert.throws(()=>f.surface.accept(f.snapshot,editor));
  f.surface.close();
}
{
  const f=fixture();await connect(f);f.document.activeElement=f.root;
  const successor=structuredClone(f.state);successor.presentation.identity.presentationRevision='2';successor.presentation.keys={fallback:'pass',rules:[]};
  f.setOnSend(operation=>{if(operation.input?.kind==='focus')f.surface.accept({...f.snapshot,revision:'2'},successor);});
  const event=f.document.emit('keydown',{key:'F5',code:'F5',location:0});
  assert.equal(event.prevented,true,'Reentrant focus delivery must not change capture basis');
  assert.equal(f.operations.at(-1).identity.presentationRevision,'1','Reentrant delivery must not rebase physical key');
  f.surface.close();
}
{
  const f=fixture();await connect(f);f.root.focus();
  f.document.activeElement=null;f.document.emit('focusout');f.host.emit('blur');
  await flush();await flush();
  const focusEvents=f.operations.filter(value=>value.input?.kind==='focus');
  assert(focusEvents.some(value=>!value.input.focused),'Pending focus receipt lost focusout');
  assert(focusEvents.some(value=>!value.input.active),'Pending focus receipt lost external blur');
  f.surface.close();
}
{
  const f=fixture();await connect(f);
  f.root.emit('pointerdown',{pointerId:1,clientX:15,clientY:25,button:0,buttons:1});
  f.root.emit('pointerdown',{pointerId:2,clientX:15,clientY:25,button:0,buttons:1});
  const successor=structuredClone(f.state);successor.presentation.identity.context='2';
  f.setOnSend(operation=>{if(operation.input?.phase==='cancel'&&operation.input.pointer==='1')f.surface.accept(f.snapshot,successor);});
  f.surface.cancelPointers();
  const cancellations=f.operations.filter(value=>value.input?.phase==='cancel');
  assert.equal(cancellations.length,2);assert(cancellations.every(value=>value.identity.context==='1'),'Cancellation batch rebased old capture onto successor');
  f.surface.close();
}
{
  for(const pointerId of [0,1]){
    const f=fixture();await connect(f);
    f.root.focus=()=>{f.host.emit('focus');f.document.activeElement=f.root;f.document.emit('focusin');};
    f.root.emit('pointerdown',{pointerId,clientX:15,clientY:25,button:0,buttons:1});
    assert(f.root.captured.has(pointerId),'First iframe focus retired its new pointer owner');
    f.root.emit('pointermove',{pointerId,clientX:215,clientY:25,button:-1,buttons:1});
    f.root.emit('pointerup',{pointerId,clientX:215,clientY:25,button:0,buttons:0});
    const pointers=f.operations.filter(value=>value.input?.kind==='pointer');
    assert.deepEqual(pointers.map(value=>value.input.phase),['down','move','up']);
    assert(pointers.every(value=>value.input.pointer===pointers[0].input.pointer));
    assert.equal(f.root.captured.size,0);f.surface.close();
  }
}
{
  for(const boundary of ['focus','capture','capabilities']){
    const f=fixture();await connect(f);const successor=structuredClone(f.state);successor.presentation.identity.context='2';
    if(boundary==='capabilities'){
      successor.presentation.identity.context='1';successor.presentation.required='33';successor.capabilities.supported='33';
      f.root.focus=()=>{f.surface.accept(f.snapshot,successor);};
    }else if(boundary==='focus')f.root.focus=()=>{f.surface.accept(f.snapshot,successor);};
    else f.root.setPointerCapture=id=>{f.root.captured.add(id);f.surface.accept(f.snapshot,successor);};
    const event=f.root.emit('pointerdown',{pointerId:0,clientX:15,clientY:25,button:0,buttons:1});
    assert(!f.operations.some(value=>value.input?.phase==='down'),'Retired acquisition resumed its outer down');
    assert.equal(f.root.captured.size,0,'Retired acquisition retained native capture');
    assert(event.prevented&&event.stopped,'Retired owned down escaped into legacy routing');
    f.surface.close();
  }
}
const mouseFixture=(classifyContext=event=>event.nativeOrigin||(event.pointerType==='mouse'?'pointer':null))=>fixture({profile:'mouse_v1',classifyContext});
const emitMouse=(f,type,values={})=>f.root.emit(type,{target:f.root,isTrusted:true,pointerType:'mouse',pointerId:0,clientX:15,clientY:25,button:type==='pointermove'?-1:0,buttons:type==='pointerdown'?1:0,...values});
const mouseOperations=f=>f.operations.filter(value=>value.input?.kind==='mouse');
const validateMouse=f=>{for(const operation of mouseOperations(f))validateSurfaceOperation(operation,f.snapshot,f.state,'mouse_v1');};
{
  const f=mouseFixture();await connect(f);
  assert.deepEqual(f.operations[0],{type:'surfaceConnect',version:1,supported:'8225',mouseInputVersion:1});
  f.surface.close();
  const partial=fixture({profile:'mouse_v1'});await connect(partial);
  assert.deepEqual(partial.operations[0],{type:'surfaceConnect',version:1,supported:'33'});
  emitMouse(partial,'pointerdown');assert.equal(mouseOperations(partial).length,0);partial.surface.close();
  assert.throws(()=>fixture({profile:'unknown'}));assert.throws(()=>fixture({profile:'mouse_v1',classifyContext:3}));
}
{
  const f=mouseFixture();await connect(f);let serial=0;
  for(const button of [0,1,2,3,4]){
    const pointerId=button%2,buttons=[1,4,2,8,16][button];
    emitMouse(f,'pointerdown',{pointerId,button,buttons,detail:99});assert(f.root.captured.has(pointerId));
    emitMouse(f,'pointerup',{pointerId,button,buttons:0,detail:3});
    const [down,up]=mouseOperations(f).slice(-2).map(value=>value.input);
    assert.equal(down.captureToken,String(++serial));assert.equal(up.captureToken,down.captureToken);
    assert.deepEqual([down.phase,up.phase,down.buttons,up.buttons,down.clicks,up.clicks],['down','up',buttons,0,0,0]);
    assert.equal(f.root.captured.size,0);
  }
  validateMouse(f);f.surface.close();
}
{
  const f=mouseFixture();await connect(f);const bits=[1,4,2,8,16];
  for(let target=1;target<32;++target){
    const ordinals=bits.map((bit,index)=>target&bit?index:-1).filter(index=>index>=0);let mask=0;
    const begin=mouseOperations(f).length;
    for(const [index,button] of ordinals.entries()){
      mask|=bits[button];emitMouse(f,index?'pointermove':'pointerdown',{button,buttons:mask});
    }
    const token=mouseOperations(f).at(-1).input.captureToken;
    emitMouse(f,'pointermove',{clientX:-15,clientY:-25,buttons:mask});
    for(const [index,button] of ordinals.entries()){
      mask&=~bits[button];emitMouse(f,index===ordinals.length-1?'pointerup':'pointermove',{button,buttons:mask});
      assert.equal(f.root.captured.has(0),mask!==0,'Partial release must retain native capture');
    }
    const events=mouseOperations(f).slice(begin).map(value=>value.input);
    assert(events.every(value=>value.captureToken===token));
    assert.equal(events.filter(value=>value.phase==='down').length,ordinals.length);
    assert.equal(events.filter(value=>value.phase==='up').length,ordinals.length);
    assert.equal(events.find(value=>value.phase==='move').x,-25);
  }
  validateMouse(f);f.surface.close();
}
{
  for(const contradiction of [{button:2,buttons:5},{button:-1,buttons:3},{button:1,buttons:7},{pointerId:9,button:-1,buttons:1}]){
    const f=mouseFixture();await connect(f);emitMouse(f,'pointerdown');
    for(const value of [{isTrusted:false},{pointerType:'touch'},{pointerType:'pen'},{pointerType:''},{pointerType:'vendor'}])emitMouse(f,'pointermove',{...value,buttons:1});
    assert(f.root.captured.has(0),'Unsupported sources cannot revoke a trusted mouse stream');
    emitMouse(f,'pointermove',contradiction);
    assert.deepEqual(mouseOperations(f).map(value=>value.input.phase),['down','cancel']);
    assert.equal(f.root.captured.size,0);
    emitMouse(f,'pointermove',{button:0,buttons:1});assert.equal(mouseOperations(f).length,2,'Idle movement must not reconstruct a missed press');
    const cancel=mouseOperations(f).at(-1).input;
    assert.deepEqual([cancel.x,cancel.y,cancel.buttons,cancel.modifiers,cancel.clicks],[0,0,0,0,0]);validateMouse(f);f.surface.close();
  }
}
{
  const f=mouseFixture();await connect(f);emitMouse(f,'pointerdown',{button:2,buttons:2});
  const token=mouseOperations(f).at(-1).input.captureToken;
  emitMouse(f,'contextmenu',{button:2,buttons:2,clientX:10,clientY:20});
  assert.equal(mouseOperations(f).at(-1).input.contextOrigin,'pointer','Zero coordinates do not imply keyboard origin');
  emitMouse(f,'contextmenu',{pointerType:'',pointerId:-1,nativeOrigin:'keyboard',clientX:NaN,clientY:NaN,buttons:0,ctrlKey:true});
  const keyboard=mouseOperations(f).at(-1).input;
  assert.deepEqual([keyboard.contextOrigin,keyboard.x,keyboard.y,keyboard.modifiers,keyboard.buttons,keyboard.captureToken],['keyboard',0,0,0,2,token]);
  const count=mouseOperations(f).length;
  const ambiguous=emitMouse(f,'contextmenu',{pointerType:'',pointerId:-1,buttons:0});
  assert(ambiguous.prevented&&ambiguous.stopped);assert.equal(mouseOperations(f).length,count);assert(f.root.captured.has(0));
  emitMouse(f,'pointerup',{button:2});assert.equal(mouseOperations(f).at(-1).input.captureToken,token);
  validateMouse(f);f.surface.close();
  for(const classifyContext of [()=>null,()=>{throw Error('unknown source');},()=>3,()=> 'keyboard']){
    const other=mouseFixture(classifyContext);await connect(other);emitMouse(other,'pointerdown');
    const before=other.operations.length;emitMouse(other,'contextmenu',{buttons:1});
    assert.equal(other.operations.length,before);assert(other.root.captured.has(0));other.surface.close();
  }
  const reentrant=mouseFixture(event=>{reentrant.surface.accept(reentrant.snapshot,{...reentrant.state,serviceActive:true});return 'pointer';});
  await connect(reentrant);emitMouse(reentrant,'pointerdown');const before=reentrant.operations.length;
  emitMouse(reentrant,'contextmenu',{buttons:1});assert.equal(reentrant.operations.length,before);assert.equal(reentrant.root.captured.size,0);reentrant.surface.close();
}
{
  const f=mouseFixture();await connect(f);emitMouse(f,'pointerdown');const token=mouseOperations(f).at(-1).input.captureToken;
  for(const [deltaMode,deltaX,deltaY,wheelX,wheelY] of [[0,.1,-.2,Math.fround(.1),Math.fround(-.2)],[1,1,-2,16,-32],[2,.5,0,50,0]]){
    emitMouse(f,'wheel',{pointerType:undefined,pointerId:undefined,deltaMode,deltaX,deltaY});
    const input=mouseOperations(f).at(-1).input;
    assert.deepEqual([input.phase,input.captureToken,input.buttons,input.wheelX,input.wheelY],['wheel',token,1,wheelX,wheelY]);
  }
  const count=mouseOperations(f).length;
  for(const value of [{deltaMode:0,deltaX:1e-50,deltaY:0},{deltaMode:0,deltaX:1000001,deltaY:1},{deltaMode:8,deltaX:1,deltaY:1},{deltaMode:0,deltaX:Infinity,deltaY:1},{isTrusted:false,deltaMode:0,deltaX:1,deltaY:1}])emitMouse(f,'wheel',value);
  assert.equal(mouseOperations(f).length,count);assert(f.root.captured.has(0));validateMouse(f);f.surface.close();
}
{
  for(const boundary of ['earlyFocus','context','capture','capabilities','close']){
    const f=mouseFixture();await connect(f);const successor=structuredClone(f.state);successor.presentation.identity.context='2';
    if(boundary==='earlyFocus')f.root.focus=()=>{f.host.emit('focus');f.document.activeElement=f.root;f.document.emit('focusin');};
    if(boundary==='context')f.root.focus=()=>f.surface.accept(f.snapshot,successor);
    if(boundary==='capture')f.root.setPointerCapture=id=>{f.root.captured.add(id);f.surface.accept(f.snapshot,successor);};
    if(boundary==='capabilities'){
      successor.presentation.identity.context='1';successor.capabilities.supported='33';delete successor.capabilities.mouseInputVersion;successor.presentation.required='33';
      f.root.focus=()=>f.surface.accept(f.snapshot,successor);
    }
    if(boundary==='close')f.root.focus=()=>f.surface.close();
    const down=emitMouse(f,'pointerdown');assert(down.prevented&&down.stopped);
    if(boundary==='earlyFocus'){
      emitMouse(f,'pointermove',{buttons:1,clientX:215});emitMouse(f,'pointerup');
      assert.deepEqual(mouseOperations(f).map(value=>value.input.phase),['down','move','up']);
    }else assert(!mouseOperations(f).some(value=>value.input.phase==='down'),'Retired acquisition cannot post an orphan down');
    assert.equal(f.root.captured.size,0);f.surface.close();
  }
}
{
  for(const terminal of ['cancel','up']){
    for(const boundary of ['send','release']){
      const f=mouseFixture();await connect(f);emitMouse(f,'pointerdown');let installed=false;
      const successor=()=>{if(installed)return;installed=true;emitMouse(f,'pointerdown');};
      if(boundary==='send')f.setOnSend(operation=>{if(operation.input?.phase===terminal)successor();});
      else f.root.releasePointerCapture=id=>{f.root.captured.delete(id);successor();f.root.emit('lostpointercapture',{isTrusted:true,pointerId:id});};
      if(terminal==='cancel')f.surface.cancelPointers();else emitMouse(f,'pointerup');
      const events=mouseOperations(f).map(value=>value.input);
      assert.deepEqual(events.map(value=>value.phase),['down',terminal,'down'],'Old terminal must precede callback successor');
      assert.notEqual(events[0].captureToken,events[2].captureToken);assert(f.root.captured.has(0),'Old cleanup released successor capture');
      f.setOnSend(null);emitMouse(f,'pointermove',{buttons:1});emitMouse(f,'pointerup');
      assert.equal(mouseOperations(f).at(-1).input.captureToken,events[2].captureToken);f.surface.close();
    }
  }
}
{
  const f=mouseFixture();await connect(f);emitMouse(f,'pointerdown');
  const first=mouseOperations(f)[0],successor=structuredClone(f.state);successor.presentation.identity.presentationRevision='2';
  f.surface.accept({...f.snapshot,revision:'2'},successor);emitMouse(f,'pointermove',{buttons:1});
  assert.equal(first.identity.presentationRevision,'1');assert.equal(mouseOperations(f).at(-1).identity.presentationRevision,'2');
  assert.equal(first.input.captureToken,mouseOperations(f).at(-1).input.captureToken);
  for(const type of ['click','dblclick','auxclick'])assert(emitMouse(f,type,{detail:1}).prevented);
  f.surface.accept({...f.snapshot,revision:'2'},{...successor,serviceActive:true});assert.equal(f.root.captured.size,0);
  const count=f.operations.length;emitMouse(f,'pointermove',{buttons:1});assert.equal(f.operations.length,count);f.surface.close();
}
{
  for(const loss of ['blur','focusout','hidden']){
    const f=mouseFixture();f.state.capabilities.supported='8192';f.state.presentation.required='8192';f.state.presentation.keys={fallback:'pass',rules:[]};await connect(f);
    emitMouse(f,'pointerdown');assert(f.root.captured.has(0));
    if(loss==='blur')f.host.emit('blur');
    else if(loss==='focusout'){f.document.activeElement=null;f.document.emit('focusout');}
    else{f.document.visibilityState='hidden';f.document.emit('visibilitychange');}
    assert.deepEqual(mouseOperations(f).map(value=>value.input.phase),['down','cancel'],'Mouse-only capture survived native loss');
    assert.equal(f.root.captured.size,0);assert(!f.operations.some(value=>value.input?.kind==='focus'),'Mouse-only profile invented focus capability');
    validateMouse(f);f.surface.close();
  }
}
console.log('browser surface physical model: ten legacy and ten mouse groups passed; no real-browser qualification');
{
  // Editor negotiation is explicit and requires the separate authoritative
  // endpoint before any native listener or surface offer can be installed.
  for(const editor of [undefined,{}, {createBridge(){}}]){
    const document=new Target(),root=new Target();
    assert.throws(()=>createBrowserSurface({root,document,profile:'editor_v1',editor,send(){},resolveOwner(){}}));
    assert.equal(document.events.size,0);assert.equal(root.events.size,0);
  }
  assert.throws(()=>createBrowserSurface({root:new Target(),document:new Target(),profile:'unknown',send(){},resolveOwner(){}}));
}
console.log('browser surface editor opt-in construction gates passed; no native editor qualification');
