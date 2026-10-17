// SPDX-License-Identifier: CC0-1.0
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import * as protocol from '../host/browser_surface_protocol.mjs';
const {validateSurfaceState, validateSurfaceOperation} = protocol;
assert.deepEqual(Object.keys(protocol).sort(), ['validateSurfaceOperation', 'validateSurfaceState']);

const clone = value => structuredClone(value);
const snapshot = () => ({revision:'9007199254740993', scale:1.5, closed:false, widgets:[{
  key:{id:'surface/é',generation:'2'}, visible:true, enabled:true, inModal:true, bounds:[10,20,200,100], clip:[20,30,100,50]
}]});
const state = () => ({version:1, capabilities:{version:1,supported:'97',limits:{
  textBytes:65536,clipboardBytes:65536,popupItems:1024,popupTextBytes:65536,captureRules:64,heldKeys:64,popupDepth:8
}},presentation:{identity:{owner:{id:'surface/é',generation:'2'},presentationRevision:'9007199254740993',generation:'3',epoch:'4',context:'5'},
  required:'97',bounds:[10,20,200,100],clip:[20,30,100,50],displayScale:1.5,available:true,
  keys:{fallback:'pass',rules:[{key:'z',code:'KeyZ',requiredModifiers:2,forbiddenModifiers:4,down:true,up:false,disposition:'capture'}]},
  editor:null,clipboard:null,popup:null},focused:true,active:true,composition:null,lastSequence:'2',serviceActive:false});
const key = () => ({kind:'key',phase:'down',key:'😀',code:'KeyZ',location:3,modifiers:31,repeat:false});
const focus = () => ({kind:'focus',focused:true,active:true,cause:'direct'});
const pointer = () => ({kind:'pointer',phase:'down',pointer:'9007199254740993',x:12.5,y:-20.5,wheelX:0,wheelY:0,button:4,buttons:31,clicks:3,modifiers:31});
const operation = (input = key()) => ({type:'surfaceInput',identity:state().presentation.identity,sequence:'4',input});
const malformed = action => assert.throws(action, error => error instanceof Error && error.stale !== true);
const stale = action => assert.throws(action, error => error instanceof Error && error.stale === true);

function validPackets() {
  const view=snapshot(), surface=state(), packet=operation();
  assert.equal(validateSurfaceState(view,null),null);
  assert.equal(validateSurfaceState(view,surface),surface);
  assert.equal(validateSurfaceOperation(packet,view,surface),packet);
  assert.equal(JSON.stringify(packet),JSON.stringify(operation()));
  assert.equal(JSON.stringify(surface),JSON.stringify(state()));
  const boundaryView=snapshot(), boundaryState=state(), boundaryKey=key();
  boundaryView.widgets[0].key.id=boundaryState.presentation.identity.owner.id='é'.repeat(64);
  boundaryKey.key='😀'.repeat(16);boundaryKey.code='A'.repeat(64);
  const boundaryPacket=operation(boundaryKey);boundaryPacket.identity=clone(boundaryState.presentation.identity);
  assert.equal(validateSurfaceOperation(boundaryPacket,boundaryView,boundaryState),boundaryPacket);
  for (const supported of ['0','1','32','64','97']) {
    const connect={type:'surfaceConnect',version:1,supported};
    assert.equal(validateSurfaceOperation(connect,null,null),connect);
  }
  for (const phase of ['down','up']) {
    const stroke=key();stroke.phase=phase;
    assert.equal(validateSurfaceOperation(operation(stroke),view,surface).input.phase,phase);
  }
  const repeated=key();repeated.repeat=true;
  assert.equal(validateSurfaceOperation(operation(repeated),view,surface).input.repeat,true);
  for (const phase of ['move','down','up','cancel','wheel','context']) {
    const input=pointer();input.phase=phase;
    if(phase==='wheel')input.wheelY=-1000000;
    assert.equal(validateSurfaceOperation(operation(input),view,surface).input.phase,phase);
  }
  for (const phase of ['move','wheel','context']) {
    const input=pointer();input.phase=phase;input.pointer='0';if(phase==='wheel')input.wheelX=1;
    assert.equal(validateSurfaceOperation(operation(input),view,surface).input.pointer,'0');
  }
  const maximum=operation();maximum.sequence='18446744073709551615';
  assert.equal(validateSurfaceOperation(maximum,view,surface),maximum);
  for (const cause of ['direct','external']) {
    const input=focus();input.cause=cause;
    const unavailable=state();unavailable.presentation.available=false;unavailable.focused=false;unavailable.active=false;
    assert.equal(validateSurfaceOperation(operation(input),view,unavailable).input.cause,cause);
  }
  const unfocused=state();unfocused.focused=false;
  assert.equal(validateSurfaceOperation(operation(pointer()),view,unfocused).input.kind,'pointer');
  const hidden=snapshot(), dormant=state();dormant.presentation.available=false;hidden.widgets[0].visible=false;
  assert.equal(validateSurfaceState(hidden,dormant),dormant);
  const noPresentation=state();noPresentation.presentation=null;
  assert.equal(validateSurfaceState(view,noPresentation),noPresentation);
  const modal=state();modal.serviceActive=true;
  assert.equal(validateSurfaceState(view,modal),modal);
  const nullPrototype=Object.assign(Object.create(null),clone(surface));
  assert.equal(validateSurfaceState(view,nullPrototype),nullPrototype);
}

function malformedState() {
  for (const edit of [
    value=>{value.extra=true;},value=>{delete value.active;},value=>{value.version='1';},value=>{value.version=2;},
    value=>{value.focused=1;},value=>{value.active=null;},value=>{value.serviceActive=0;},value=>{value.composition='1';},
    value=>{value.lastSequence=3;},value=>{value.lastSequence='01';},value=>{value.lastSequence='18446744073709551616';},
    value=>{value.capabilities.extra=0;},value=>{value.capabilities.version=true;},value=>{value.capabilities.supported=97;},
    value=>{value.capabilities.supported='98';},value=>{value.capabilities.supported='4294967393';},
    value=>{value.capabilities.limits.heldKeys=65;},value=>{value.capabilities.limits.captureRules=0;},
    value=>{value.capabilities.limits.textBytes=65536.5;},value=>{value.capabilities.limits.popupDepth='8';},
    value=>{value.capabilities.limits.extra=1;},value=>{delete value.capabilities.limits.popupItems;},
    value=>{value.presentation.extra=0;},value=>{value.presentation.required='98';},value=>{value.presentation.available=1;},
    value=>{value.presentation.editor={};},value=>{value.presentation.clipboard={};},value=>{value.presentation.popup={};},
    value=>{value.presentation.displayScale=Infinity;},value=>{value.presentation.displayScale=0;},value=>{value.presentation.displayScale=17;},
    value=>{value.presentation.bounds[0]=NaN;},value=>{value.presentation.clip[2]=-1;},value=>{value.presentation.clip[0]=0;},
    value=>{value.presentation.bounds.push(0);},value=>{value.presentation.clip[2]=1000001;},
    value=>{value.presentation.identity.context='0';},value=>{value.presentation.identity.extra=0;},
    value=>{value.presentation.identity.owner.generation='02';},value=>{value.presentation.identity.owner.extra=0;},
    value=>{value.presentation.identity.owner.id='\ud800';},value=>{value.presentation.identity.owner.id='a\0b';},
    value=>{value.presentation.identity.owner.id='é'.repeat(65);},
    value=>{value.presentation.keys.extra=0;},value=>{value.presentation.keys.fallback='default';},
    value=>{value.presentation.keys.rules=Array.from({length:65},()=>clone(value.presentation.keys.rules[0]));},
    value=>{value.presentation.keys.rules[0].key='😀'.repeat(17);},
    value=>{value.presentation.keys.rules[0].code='Key Z';},value=>{value.presentation.keys.rules[0].requiredModifiers=32;},
    value=>{value.presentation.keys.rules[0].requiredModifiers=4;},value=>{value.presentation.keys.rules[0].up='false';},
    value=>{value.presentation.keys.rules[0].down=false;},value=>{value.presentation.keys.rules[0].disposition='unknown';},
    value=>{value.presentation.keys.rules[0].extra=true;}
  ]) {const value=state();edit(value);malformed(()=>validateSurfaceState(snapshot(),value));}
  for (const value of [undefined,false,[],{},new Date()]) malformed(()=>validateSurfaceState(snapshot(),value));
  for (const edit of [
    value=>{value.revision='3';},value=>{value.scale=2;},value=>{value.widgets[0].key.generation='3';},
    value=>{value.widgets=[];},value=>{value.widgets.push(clone(value.widgets[0]));},value=>{value.widgets[0].visible=false;},
    value=>{value.widgets[0].enabled=false;},value=>{value.widgets[0].inModal=false;},
    value=>{value.widgets[0].bounds[0]+=1;},value=>{value.widgets[0].clip[2]-=1;}
  ]) {const value=snapshot();edit(value);malformed(()=>validateSurfaceState(value,state()));}
  let read=false;const getter=state();Object.defineProperty(getter,'focused',{get(){read=true;return true;},enumerable:true});
  malformed(()=>validateSurfaceState(snapshot(),getter));assert.equal(read,false);
  const hidden=state();Object.defineProperty(hidden,'focused',{value:true,enumerable:false});
  malformed(()=>validateSurfaceState(snapshot(),hidden));
  const symbol=state();symbol[Symbol('extra')]=true;malformed(()=>validateSurfaceState(snapshot(),symbol));
  const sparse=state();sparse.presentation.bounds=Array(4);malformed(()=>validateSurfaceState(snapshot(),sparse));
  const decorated=state();decorated.presentation.bounds.extra=1;malformed(()=>validateSurfaceState(snapshot(),decorated));
  let iterated=false;class ArraySubclass extends Array { *[Symbol.iterator](){iterated=true;yield 0;} }
  const exotic=state();exotic.presentation.bounds=new ArraySubclass(10,20,200,100);
  malformed(()=>validateSurfaceState(snapshot(),exotic));assert.equal(iterated,false);
}

function malformedOperations() {
  for (const supported of [97,97n,'','00','+1','-1','1.0',' 1','98','18446744073709551616'])
    malformed(()=>validateSurfaceOperation({type:'surfaceConnect',version:1,supported},snapshot(),null));
  for (const version of [true,'1',0,2,1.5]) malformed(()=>validateSurfaceOperation({type:'surfaceConnect',version,supported:'97'},snapshot(),null));
  malformed(()=>validateSurfaceOperation({type:'surfaceConnect',version:1,supported:'97',limits:{}},snapshot(),null));
  malformed(()=>validateSurfaceOperation({type:'surfaceConnect',version:1,supported:'97'},{...snapshot(),closed:0},null));
  for (const sequence of [1,1n,true,null,'','0','01','+1','-1','1.0',' 1','18446744073709551616']) {
    const value=operation();value.sequence=sequence;malformed(()=>validateSurfaceOperation(value,snapshot(),state()));
  }
  for (const id of ['', 'é'.repeat(65), '\ud800','\udc00','a\0b']) {
    const value=operation();value.identity.owner.id=id;malformed(()=>validateSurfaceOperation(value,snapshot(),state()));
  }
  for(const field of ['owner','presentationRevision','generation','epoch','context']) {
    const value=operation();delete value.identity[field];malformed(()=>validateSurfaceOperation(value,snapshot(),state()));
  }
  for (const kind of ['text','composition','selection','clipboard','popup','service','unknown']) {
    const value=operation();value.input.kind=kind;malformed(()=>validateSurfaceOperation(value,snapshot(),state()));
  }
  for (const cause of ['owned_service','owned_popup','unknown']) {
    const value=focus();value.cause=cause;malformed(()=>validateSurfaceOperation(operation(value),snapshot(),state()));
  }
  for (const edit of [
    value=>{value.phase='press';},value=>{value.phase='up';value.repeat=true;},value=>{value.repeat=0;},
    value=>{value.key='';},value=>{value.key='😀'.repeat(17);},value=>{value.key='\ud800';},value=>{value.key='a\0b';},
    value=>{value.code='Key Z';},value=>{value.code='é';},value=>{value.location=4;},value=>{value.location=1.5;},
    value=>{value.modifiers=32;},value=>{value.modifiers=-1;},value=>{value.modifiers=true;},value=>{value.extra=0;},value=>{delete value.code;}
  ]) {const value=key();edit(value);malformed(()=>validateSurfaceOperation(operation(value),snapshot(),state()));}
  for (const edit of [
    value=>{value.phase='press';},value=>{value.pointer='0';},value=>{value.pointer=1;},value=>{value.pointer='01';},
    value=>{value.x=Infinity;},value=>{value.y=NaN;},value=>{value.x=1000001;},value=>{value.wheelX=1;},
    value=>{value.phase='wheel';},value=>{value.button=5;},value=>{value.buttons=32;},value=>{value.clicks=0;},
    value=>{value.clicks=1.5;},value=>{value.modifiers=32;},value=>{value.modifiers='1';},value=>{value.extra=0;}
  ]) {const value=pointer();edit(value);malformed(()=>validateSurfaceOperation(operation(value),snapshot(),state()));}
  const extra=operation();extra.operation='service';malformed(()=>validateSurfaceOperation(extra,snapshot(),state()));
  for(const [value,field] of [[operation(),'type'],[key(),'kind']]) {
    let read=false;Object.defineProperty(value,field,{get(){read=true;return field==='type'?'surfaceInput':'key';},enumerable:true});
    malformed(()=>validateSurfaceOperation(field==='type'?value:operation(value),snapshot(),state()));assert.equal(read,false);
  }
  for(const value of [null,undefined,false,[],{},new Date()])malformed(()=>validateSurfaceOperation(value,snapshot(),state()));
}

function staleOperations() {
  const view=snapshot(), surface=state();
  stale(()=>validateSurfaceOperation({type:'surfaceConnect',version:1,supported:'97'},view,surface));
  stale(()=>validateSurfaceOperation({type:'surfaceConnect',version:1,supported:'97'},{...view,closed:true},null));
  stale(()=>validateSurfaceOperation(operation(),view,null));
  const absent=state();absent.presentation=null;stale(()=>validateSurfaceOperation(operation(),view,absent));
  let read=false;const getter=snapshot();Object.defineProperty(getter,'closed',{get(){read=true;return false;},enumerable:true});
  stale(()=>validateSurfaceOperation(operation(),getter,null));stale(()=>validateSurfaceOperation(operation(),getter,absent));assert.equal(read,false);
  const closed=snapshot();closed.closed=true;stale(()=>validateSurfaceOperation(operation(),closed,surface));
  for(const field of ['presentationRevision','generation','epoch','context']) {
    const value=operation();value.identity[field]='6';stale(()=>validateSurfaceOperation(value,view,surface));
  }
  for(const field of ['id','generation']) {
    const value=operation();value.identity.owner[field]=field==='id'?'another':'6';stale(()=>validateSurfaceOperation(value,view,surface));
  }
  for(const sequence of ['1','2']) {const value=operation();value.sequence=sequence;stale(()=>validateSurfaceOperation(value,view,surface));}
  const exhausted=state();exhausted.lastSequence='18446744073709551615';stale(()=>validateSurfaceOperation(operation(),view,exhausted));
  for(const field of ['serviceActive','focused','active']) {
    const value=state();value[field]=field==='serviceActive';stale(()=>validateSurfaceOperation(operation(),view,value));
  }
  const unavailable=state();unavailable.presentation.available=false;stale(()=>validateSurfaceOperation(operation(),view,unavailable));
  stale(()=>validateSurfaceOperation(operation(pointer()),view,unavailable));
  const inactive=state();inactive.active=false;stale(()=>validateSurfaceOperation(operation(pointer()),view,inactive));
  for(const [input,supported] of [[key(),'96'],[focus(),'65'],[pointer(),'33']]) {
    const value=state();value.capabilities.supported=supported;value.presentation.required=supported;
    if(supported==='96')value.presentation.keys.rules=[];
    stale(()=>validateSurfaceOperation(operation(input),view,value));
  }
  const malformedStale=operation();malformedStale.sequence='01';
  malformed(()=>validateSurfaceOperation(malformedStale,closed,null));
}

function mouseSuccessor() {
  const profile = 'mouse_v1';
  const surface = () => {
    const value = state(); value.capabilities.supported = value.presentation.required = '8225';
    value.capabilities.mouseInputVersion = 1; return value;
  };
  const mouse = () => ({kind:'mouse',version:1,phase:'down',captureToken:'9007199254740993',x:12.5,y:-20.5,
    wheelX:0,wheelY:0,button:4,buttons:16,clicks:0,modifiers:31,contextOrigin:'pointer'});
  const connect = () => ({type:'surfaceConnect',version:1,supported:'8225',mouseInputVersion:1});
  const accept = value => validateSurfaceOperation(operation(value),snapshot(),surface(),profile);
  const initial = surface(), connection = connect(), packet = operation(mouse());
  assert.equal(validateSurfaceState(snapshot(),initial,profile),initial);
  assert.equal(validateSurfaceOperation(connection,null,null,profile),connection);
  assert.equal(validateSurfaceOperation(packet,snapshot(),initial,profile),packet);
  assert.equal(packet.input.captureToken,'9007199254740993');
  malformed(()=>validateSurfaceState(snapshot(),initial));
  malformed(()=>validateSurfaceOperation(connection,null,null));
  malformed(()=>validateSurfaceOperation(operation(mouse()),snapshot(),state()));
  malformed(()=>validateSurfaceState(snapshot(),state(),profile)); // raw_pointer64 stays in the legacy profile.
  malformed(()=>validateSurfaceOperation(operation(pointer()),snapshot(),initial,profile));
  for (const supported of ['0','1','32','33']) {
    const value = connect(); value.supported = supported;
    malformed(()=>validateSurfaceOperation(value,null,null,profile));
    delete value.mouseInputVersion;
    assert.equal(validateSurfaceOperation(value,null,null,profile),value);
  }
  const noMarker = connect(); delete noMarker.mouseInputVersion;
  malformed(()=>validateSurfaceOperation(noMarker,null,null,profile));
  for (const version of [undefined,0,2,true,'1',1.5]) {
    const value = connect(); value.mouseInputVersion = version;
    malformed(()=>validateSurfaceOperation(value,null,null,profile));
    const current = surface(); current.capabilities.mouseInputVersion = version;
    malformed(()=>validateSurfaceState(snapshot(),current,profile));
  }
  for (const supported of ['64','97','8289','16384','18446744073709551615']) {
    const value = connect(); value.supported = supported;
    malformed(()=>validateSurfaceOperation(value,null,null,profile));
  }
  const absent = surface(); absent.capabilities.supported = absent.presentation.required = '33';
  malformed(()=>validateSurfaceState(snapshot(),absent,profile));
  delete absent.capabilities.mouseInputVersion;
  assert.equal(validateSurfaceState(snapshot(),absent,profile),absent);
  stale(()=>validateSurfaceOperation(operation(mouse()),snapshot(),absent,profile));
  for (let button=0;button!==5;++button) for (let clicks=0;clicks!==4;++clicks) {
    const value=mouse();value.button=button;value.buttons=[1,4,2,8,16][button];value.clicks=clicks;
    assert.equal(accept(value).input.button,button);
    value.phase='up';value.buttons=0;assert.equal(accept(value).input.phase,'up');
  }
  for (const phase of ['move','wheel','cancel','context']) {
    const value=mouse();value.phase=phase;value.button=0;
    if(phase==='wheel')value.wheelX=Math.fround(0.1);
    if(phase==='cancel'){value.x=0;value.y=0;value.buttons=0;value.modifiers=0;}
    assert.equal(accept(value).input.captureToken,'9007199254740993');
    if(phase!=='cancel'){value.captureToken='0';value.buttons=0;assert.equal(accept(value).input.captureToken,'0');}
  }
  const heldContext=mouse();heldContext.phase='context';heldContext.button=0;heldContext.contextOrigin='keyboard';
  heldContext.x=heldContext.y=heldContext.modifiers=0;
  assert.equal(accept(heldContext).input.buttons,16);
  assert.equal(accept(heldContext).input.captureToken,'9007199254740993');
  const maximum=mouse();maximum.captureToken='18446744073709551615';
  assert.equal(accept(maximum).input.captureToken,'18446744073709551615');
  for (const edit of [
    value=>{value.version=0;},value=>{value.version=2;},value=>{value.version='1';},value=>{value.version=true;},
    value=>{value.phase='press';},value=>{value.captureToken='0';},value=>{value.captureToken='01';},
    value=>{value.captureToken=1;},value=>{value.captureToken='18446744073709551616';},
    value=>{value.button=5;},value=>{value.buttons=32;},value=>{value.buttons=0;},value=>{value.phase='up';},
    value=>{value.clicks=-1;},value=>{value.clicks=4;},value=>{value.clicks=0.5;},value=>{value.modifiers=32;},
    value=>{value.x=1000001;},value=>{value.y=Infinity;},value=>{value.wheelX=1;},
    value=>{value.contextOrigin='keyboard';},value=>{value.contextOrigin='unknown';},
    value=>{value.pointer='1';},value=>{value.token=value.captureToken;delete value.captureToken;},
    value=>{value.phase='move';},value=>{value.phase='context';},value=>{value.phase='cancel';}
  ]) {const value=mouse();edit(value);malformed(()=>accept(value));}
  for(const field of Object.keys(mouse())) {
    const value=mouse();delete value[field];malformed(()=>accept(value));
  }
  const move=mouse();move.phase='move';move.button=0;move.clicks=1;malformed(()=>accept(move));
  move.clicks=0;move.captureToken='0';malformed(()=>accept(move));
  const wheel=mouse();wheel.phase='wheel';wheel.button=0;
  malformed(()=>accept(wheel));wheel.wheelX=0.1;malformed(()=>accept(wheel));
  wheel.wheelX=Math.fround(0.1);assert.equal(accept(wheel).input.wheelX,Math.fround(0.1));
  const cancel=mouse();cancel.phase='cancel';cancel.button=cancel.buttons=cancel.x=cancel.y=cancel.modifiers=0;
  for(const field of ['x','y','wheelX','wheelY','button','buttons','clicks','modifiers']) {
    const value=clone(cancel);value[field]=1;malformed(()=>accept(value));
  }
  cancel.captureToken='0';malformed(()=>accept(cancel));
  for(const field of ['x','y','modifiers']) {
    const value=clone(heldContext);value[field]=1;malformed(()=>accept(value));
  }
  for(const edit of [
    value=>{value.serviceActive=true;},value=>{value.active=false;},value=>{value.presentation.available=false;},
    value=>{value.lastSequence='4';},value=>{value.presentation.identity.context='6';}
  ]) {const value=surface();edit(value);stale(()=>validateSurfaceOperation(operation(mouse()),snapshot(),value,profile));}
  const unfocused=surface();unfocused.focused=false;
  assert.equal(validateSurfaceOperation(operation(mouse()),snapshot(),unfocused,profile).input.kind,'mouse');
  for(const invalidProfile of [null,false,{},'mouse','mouse-v1','unknown']) {
    malformed(()=>validateSurfaceState(null,null,invalidProfile));
    malformed(()=>validateSurfaceOperation(connection,null,null,invalidProfile));
  }
  let read=false;const getter=mouse();Object.defineProperty(getter,'captureToken',{get(){read=true;return'1';},enumerable:true});
  malformed(()=>accept(getter));assert.equal(read,false);
  const badMarker=surface();Object.defineProperty(badMarker.capabilities,'mouseInputVersion',{get(){read=true;return 1;},enumerable:true});
  malformed(()=>validateSurfaceState(snapshot(),badMarker,profile));assert.equal(read,false);
}

function editorSuccessor() {
  const profile = 'editor_v1', maximum = '18446744073709551615', transaction = '9007199254740995';
  const context = () => ({revision:maximum,compositionTransaction:'0',surrounding:'Aé😀e\u0301Z',
    selection:[1,7],selectionBackward:true,caret:[12.5,22,1,18],editable:true,inputPurpose:'text'});
  const surface = (supported='8255') => {
    const value=state();value.version=2;value.profile=profile;
    value.capabilities.supported=value.presentation.required=supported;
    if(BigInt(supported)&8192n)value.capabilities.mouseInputVersion=1;
    if(!(BigInt(supported)&1n))value.presentation.keys.rules=[];
    value.presentation.editor=BigInt(supported)&8n?context():null;
    return value;
  };
  const connect = (supported='8255') => ({type:'surfaceConnect',version:2,profile,supported,
    ...(BigInt(supported)&8192n?{mouseInputVersion:1}:{})});
  const commit = () => ({kind:'text',transaction,editorRevision:maximum,text:'é😀',replacement:[1,7]});
  const composition = (operation='begin') => ({kind:'composition',operation,transaction,editorRevision:maximum,
    text:operation==='cancel'?'':'é😀',selection:operation==='cancel'?[0,0]:[2,6],replacement:null});
  const selection = () => ({kind:'selection',editorRevision:maximum,selection:[7,10],backward:true});
  const accept = (input, current=surface()) => validateSurfaceOperation(operation(input),snapshot(),current,profile);
  const active = (attestation=transaction) => {
    const current=surface();current.composition=transaction;current.presentation.editor.compositionTransaction=attestation;return current;
  };
  const current=surface(), packet=operation(commit());
  assert.equal(validateSurfaceState(snapshot(),current,profile),current);
  assert.equal(validateSurfaceOperation(packet,snapshot(),current,profile),packet);
  const copied=JSON.parse(JSON.stringify(current));
  assert.equal(validateSurfaceState(snapshot(),copied,profile),copied);
  assert.equal(copied.presentation.editor.revision,maximum);
  assert.deepEqual(copied.presentation.editor.selection,[1,7]);
  assert.equal(accept(commit()).input.transaction,transaction);
  assert.equal(accept(selection()).input.backward,true);
  assert.equal(accept(composition()).input.selection[1],6);
  for(const attestation of ['0',transaction]) {
    const live=active(attestation);
    assert.equal(validateSurfaceState(snapshot(),live,profile),live);
    for(const phase of ['update','commit','cancel']) assert.equal(accept(composition(phase),live).input.operation,phase);
  }
  for(const oldProfile of ['legacy','mouse_v1']) {
    malformed(()=>validateSurfaceState(snapshot(),current,oldProfile));
    malformed(()=>validateSurfaceOperation(connect(),null,null,oldProfile));
    for(const input of [commit(),composition(),selection()]) malformed(()=>validateSurfaceOperation(operation(input),snapshot(),current,oldProfile));
  }
  for(const old of [state(),{...current,version:1}]) malformed(()=>validateSurfaceState(snapshot(),old,profile));
  malformed(()=>validateSurfaceOperation({type:'surfaceConnect',version:1,supported:'63'},null,null,profile));
  // Every admitted subset is value negotiation, not a claim of physical support.
  const bits=[1n,2n,4n,8n,16n,32n,8192n];
  for(let mask=0;mask<128;++mask) {
    const supported=String(bits.reduce((value,bit,index)=>value|(mask&(1<<index)?bit:0n),0n));
    const connection=connect(supported), subset=surface(supported);
    assert.equal(validateSurfaceOperation(connection,null,null,profile),connection);
    assert.equal(validateSurfaceState(snapshot(),subset,profile),subset);
  }
  for(const supported of ['64','97','128','256','512','1024','2048','4096','16319','18446744073709551615']) {
    const value=connect();value.supported=supported;
    malformed(()=>validateSurfaceOperation(value,null,null,profile));
  }
  for(const edit of [value=>{value.version=1;},value=>{value.version='2';},value=>{value.profile='mouse_v1';},
    value=>{delete value.profile;},value=>{value.extra=true;},value=>{delete value.mouseInputVersion;},
    value=>{value.mouseInputVersion=2;},value=>{value.limits={};}]) {
    const value=connect();edit(value);malformed(()=>validateSurfaceOperation(value,null,null,profile));
  }
  const unexpectedMarker=connect('63');unexpectedMarker.mouseInputVersion=1;
  malformed(()=>validateSurfaceOperation(unexpectedMarker,null,null,profile));
  for(const edit of [
    value=>{value.profile='legacy';},value=>{delete value.profile;},value=>{value.version=1;},
    value=>{value.capabilities.version=2;},value=>{value.capabilities.supported='16319';},
    value=>{value.presentation.clipboard={};},value=>{value.presentation.popup={};},
    value=>{value.composition='0';},value=>{value.composition=1;},value=>{value.composition='01';},
    value=>{value.composition=maximum+'0';},value=>{value.presentation.editor.compositionTransaction=transaction;},
    value=>{value.presentation.editor.revision='0';},value=>{value.presentation.editor.revision=9007199254740993;},
    value=>{value.presentation.editor.compositionTransaction='01';},
    value=>{value.presentation.editor.surrounding='x\0y';},value=>{value.presentation.editor.surrounding='\ud800';},
    value=>{value.presentation.editor.surrounding='é'.repeat(32769);},
    value=>{value.presentation.editor.selection=[2,3];},value=>{value.presentation.editor.selection=[3,5];},
    value=>{value.presentation.editor.selection=[7,3];},value=>{value.presentation.editor.selection=[0,12];},
    value=>{value.presentation.editor.selection=[0,'1'];},value=>{value.presentation.editor.selection=[0,0.5];},
    value=>{value.presentation.editor.selection.push(0);},value=>{value.presentation.editor.selectionBackward=1;},
    value=>{value.presentation.editor.caret=[0,0,-1,1];},value=>{value.presentation.editor.caret=[0,Infinity,1,1];},
    value=>{value.presentation.editor.editable=1;},value=>{value.presentation.editor.inputPurpose='é'.repeat(33);},
    value=>{value.presentation.editor.extra=0;},value=>{delete value.presentation.editor.selectionBackward;}
  ]) {const value=surface();edit(value);malformed(()=>validateSurfaceState(snapshot(),value,profile));}
  for(const edit of [value=>{value.presentation.editor=null;},value=>{value.presentation=null;},
    value=>{value.presentation.editor.editable=false;},value=>{value.presentation.editor.compositionTransaction='6';},
    value=>{value.capabilities.supported=value.presentation.required='8251';},value=>{value.presentation.available=false;},
    value=>{value.focused=false;},value=>{value.active=false;},value=>{value.serviceActive=true;}]) {
    const value=active();edit(value);malformed(()=>validateSurfaceState(snapshot(),value,profile));
  }
  const withoutSurrounding=surface();withoutSurrounding.capabilities.supported=withoutSurrounding.presentation.required='8247';
  malformed(()=>validateSurfaceState(snapshot(),withoutSurrounding,profile));
  const bounded=surface();bounded.capabilities.limits.textBytes=10;
  malformed(()=>validateSurfaceState(snapshot(),bounded,profile));
  const readonly=surface();readonly.presentation.editor.editable=false;
  assert.equal(accept(selection(),readonly).input.kind,'selection');
  for(const input of [commit(),composition()]) stale(()=>accept(input,readonly));
  for(const input of [commit(),composition(),selection()]) {
    const value=clone(input);value.editorRevision='9007199254740993';stale(()=>accept(value));
    for(const field of Object.keys(input)) {
      const missing=clone(input);delete missing[field];malformed(()=>accept(missing));
    }
    const extra=clone(input);extra.source_key_sequence='1';malformed(()=>accept(extra));
    for(const bad of [0,1,true,null,'0','01','18446744073709551616']) {
      const invalid=clone(input);invalid.editorRevision=bad;malformed(()=>accept(invalid));
      if(input.kind!=='selection'){invalid.editorRevision=maximum;invalid.transaction=bad;malformed(()=>accept(invalid));}
    }
  }
  for(const input of [commit(),composition()]) for(const bad of ['a\0b','\udc00','é'.repeat(32769)]) {
    const value=clone(input);value.text=bad;malformed(()=>accept(value));
  }
  for(const bad of [[2,3],[3,5],[8,9],[0,12],[7,3],[-1,1],[0,65537],[0,1.5],[0,'1'],[0,1,2]]) {
    const text=commit();text.replacement=bad;malformed(()=>accept(text));
    const selected=selection();selected.selection=bad;malformed(()=>accept(selected));
    const preedit=composition();preedit.replacement=bad;malformed(()=>accept(preedit));
  }
  const deletion=commit();deletion.text='';assert.equal(accept(deletion).input.text,'');
  deletion.replacement=[1,1];malformed(()=>accept(deletion));
  malformed(()=>validateSurfaceOperation(operation(deletion),{...snapshot(),closed:true},null,profile));
  deletion.replacement=null;assert.equal(accept(deletion).input.text,'');
  const collapsed=surface();collapsed.presentation.editor.selection=[1,1];malformed(()=>accept(deletion,collapsed));
  const maximumText=commit();maximumText.text='é'.repeat(32768);
  assert.equal(accept(maximumText).input.text.length,32768);
  const tiny=surface();tiny.capabilities.limits.textBytes=11;
  const tooLarge=commit();tooLarge.text='a'.repeat(12);malformed(()=>accept(tooLarge,tiny));
  for(const bad of [[1,2],[2,3],[0,7],[6,2]]) {
    const value=composition();value.selection=bad;malformed(()=>accept(value));
  }
  for(const phase of ['update','commit','cancel']) {
    const value=composition(phase);value.replacement=[1,7];malformed(()=>accept(value,active()));
    stale(()=>accept(composition(phase)));
  }
  const badCancel=composition('cancel');badCancel.text='x';badCancel.selection=[0,1];malformed(()=>accept(badCancel,active()));
  const invalidPhase=composition();invalidPhase.operation='finish';malformed(()=>accept(invalidPhase));
  stale(()=>accept(composition(),active()));stale(()=>accept(commit(),active()));
  const wrongTransaction=composition('update');wrongTransaction.transaction='9007199254740996';
  stale(()=>accept(wrongTransaction,active()));
  for(const input of [commit(),composition(),selection()]) {
    const unfocused=surface();unfocused.focused=false;stale(()=>accept(input,unfocused));
    const missingEditor=surface();missingEditor.presentation.editor=null;stale(()=>accept(input,missingEditor));
    const missingCapability=surface();const bit=input.kind==='text'?2n:input.kind==='composition'?4n:16n;
    missingCapability.capabilities.supported=missingCapability.presentation.required=String(8255n&~bit);
    stale(()=>accept(input,missingCapability));
  }
  let read=false;
  const getter=surface();Object.defineProperty(getter.presentation.editor,'revision',{get(){read=true;return maximum;},enumerable:true});
  malformed(()=>validateSurfaceState(snapshot(),getter,profile));assert.equal(read,false);
  const operationGetter=commit();Object.defineProperty(operationGetter,'replacement',{get(){read=true;return null;},enumerable:true});
  malformed(()=>accept(operationGetter));assert.equal(read,false);
  const sparse=selection();sparse.selection=Array(2);malformed(()=>accept(sparse));
  const decorated=selection();decorated.selection.extra=0;malformed(()=>accept(decorated));
  for(const kind of ['clipboard','popup','service','unknown']) {
    const value=commit();value.kind=kind;malformed(()=>accept(value));
  }
}

function cppEditorInteroperability(path) {
  const cases=JSON.parse(readFileSync(path,'utf8'));
  assert(Array.isArray(cases)&&cases.length>=10,'C++ editor fixture inventory is incomplete');
  const kinds=new Set(),phases=new Set();let pending=false,attested=false;
  for(const value of cases) {
    assert.deepEqual(Object.keys(value).sort(),['operation','snapshot','surface']);
    const copy=JSON.parse(JSON.stringify(value));
    for(const fixture of [value,copy]) {
      assert.equal(validateSurfaceState(fixture.snapshot,fixture.surface,'editor_v1'),fixture.surface);
      assert.equal(validateSurfaceOperation(fixture.operation,fixture.snapshot,fixture.surface,'editor_v1'),fixture.operation);
    }
    assert.deepEqual(copy,value);
    kinds.add(value.operation.input.kind);
    if(value.operation.input.kind==='composition')phases.add(value.operation.input.operation);
    if(value.surface.composition!==null) {
      if(value.surface.presentation.editor.compositionTransaction==='0')pending=true;
      else attested=true;
    }
  }
  assert.deepEqual([...kinds].sort(),['composition','focus','key','mouse','selection','text']);
  assert.deepEqual([...phases].sort(),['begin','cancel','commit','update']);
  assert(pending&&attested,'C++ fixtures omitted native attestation states');
  console.log(`C++ editor serializer/decoder interoperability: ${cases.length} cases passed`);
}

validPackets();malformedState();malformedOperations();staleOperations();mouseSuccessor();editorSuccessor();
if(process.argv[2])cppEditorInteroperability(process.argv[2]);
console.log('Browser surface pure-data protocol shape, scalar, precision, capability, currentness and admission checks passed');
