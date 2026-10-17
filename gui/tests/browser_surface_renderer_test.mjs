import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const {Renderer,identity}=await import(pathToFileURL(process.argv[2]));
const mouseProfile=process.argv[3]==='mouse_v1',features=mouseProfile?'8225':'97';
class Element{
  constructor(document){this.document=document;this.events=new Map();this.children=[];this.style={};this.dataset={};this.captured=new Set();}
  addEventListener(type,callback,options){const list=this.events.get(type)||[];list.push({callback,capture:options===true||!!options?.capture});this.events.set(type,list);}
  removeEventListener(type,callback){this.events.set(type,(this.events.get(type)||[]).filter(item=>item.callback!==callback));}
  append(child){this.children.push(child);child.parent=this;}
  setAttribute(){}
  getBoundingClientRect(){return {left:0,top:0};}
  contains(value){for(let node=value;node;node=node.parent)if(node===this)return true;return false;}
  focus(){this.document.activeElement=this;this.emit('focusin');this.emit('focus');}
  setPointerCapture(id){this.captured.add(id);}
  releasePointerCapture(id){this.captured.delete(id);this.emit('lostpointercapture',{pointerId:id});}
  emit(type,values={}){
    const event={type,key:'',code:'',button:0,buttons:0,pointerId:1,clientX:5,clientY:5,location:0,detail:1,repeat:false,defaultPrevented:false,stopped:false,
      preventDefault(){this.defaultPrevented=true;},stopImmediatePropagation(){this.stopped=true;},stopPropagation(){this.stopped=true;},target:this,...values};
    const path=[];for(let node=this;node;node=node.parent)path.push(node);
    for(const node of [...path].reverse())for(const item of node.events.get(type)||[])if(item.capture&&!event.stopped)item.callback(event);
    for(const node of path)for(const item of node.events.get(type)||[])if(!item.capture&&!event.stopped)item.callback(event);
    return event;
  }
}
const document=new Element(null);document.document=document;document.createElement=()=>new Element(document);document.defaultView=new Element(document);document.defaultView.PointerEvent=class{};
const root=new Element(document),pages=new Element(document);root.parent=document;
const sent=[];const renderer=new Renderer(root,pages,operation=>{sent.push(operation);return Promise.resolve({});},document,{surface:mouseProfile?{profile:'mouse_v1',classifyContext:event=>event.pointerType==='mouse'?'pointer':null}:{}});
const key={id:'surface',generation:'1'},widget={kind:2,key,visible:true,enabled:true,inModal:true,bounds:[0,0,100,100],clip:[0,0,100,100],pointerInput:false,contextInput:false,actions:[],options:[],submit:0};
const entry=renderer.create(widget);renderer.nodes.set(identity(key),entry);
const snapshot={revision:'1',scale:1,widgets:[widget],closed:false,keyBindings:[{key:6,control:false,shift:false,alt:false}],popup:null};
const surface={version:1,capabilities:{version:1,supported:features,...(mouseProfile?{mouseInputVersion:1}:{}),limits:{textBytes:65536,clipboardBytes:65536,popupItems:1024,popupTextBytes:65536,captureRules:64,heldKeys:64,popupDepth:8}},
  presentation:{identity:{owner:key,presentationRevision:'1',generation:'7',epoch:'1',context:'1'},required:features,bounds:[0,0,100,100],clip:[0,0,100,100],displayScale:1,available:true,
    keys:{fallback:'pass',rules:[{key:'F5',code:'',requiredModifiers:0,forbiddenModifiers:0,down:true,up:true,disposition:'capture'}]},editor:null,clipboard:null,popup:null},focused:false,active:true,composition:null,lastSequence:'0',serviceActive:false};
renderer.acceptSnapshot(snapshot,surface);await renderer.connectSurface();assert.equal(sent.length,1);assert.equal(sent[0].type,'surfaceConnect');
assert.equal(sent[0].supported,features);if(mouseProfile)assert.equal(sent[0].mouseInputVersion,1);
entry.control.focus();await Promise.resolve();assert.equal(sent.length,2);assert.equal(sent[1].type,'surfaceInput');assert.equal(sent[1].input.kind,'focus','Owned focus must bypass legacy focus handler');
renderer.acceptSnapshot(snapshot,{...surface,focused:true,lastSequence:'1'});
entry.control.emit('pointerdown',{buttons:1,...(mouseProfile?{pointerType:'mouse',isTrusted:true}:{})});entry.control.emit('pointerup',mouseProfile?{pointerType:'mouse',isTrusted:true}:{});entry.control.emit('click');
assert.deepEqual(sent.slice(2).map(value=>value.input?.phase),['down','up'],'Native click must not duplicate typed raw input');
const keyboard=entry.control.emit('keydown',{key:'F5',code:'F5'});assert(keyboard.defaultPrevented);assert.equal(sent.at(-1).input.kind,'key');
assert(!sent.some(value=>value.type==='shortcut'||value.type==='activate'||value.type==='focus'),'Legacy semantic route duplicated a surface event');
assert.equal(renderer.resolveSurfaceOwner(key,{clientX:5,clientY:5,target:{closest:()=>({dataset:{key:JSON.stringify(['removed-overlay','1'])}})}}),null,'Removed painted overlay was retargeted into current surface');
const offsetWidget={...widget,bounds:[20,30,100,100],clip:[20,30,100,100]};
const keyOnly=structuredClone(surface);keyOnly.capabilities.supported='33';keyOnly.presentation.required='33';keyOnly.presentation.bounds=offsetWidget.bounds;keyOnly.presentation.clip=offsetWidget.clip;keyOnly.focused=true;
delete keyOnly.capabilities.mouseInputVersion;
renderer.acceptSnapshot({...snapshot,widgets:[offsetWidget]},keyOnly);
const beforeKeyboardClick=sent.length;entry.control.emit('click',{detail:0,clientX:0,clientY:0});
assert.equal(sent.length,beforeKeyboardClick,'Keyboard synthetic click leaked legacy activate without pointer capability or hit coordinates');
renderer.destroy();const count=sent.length;entry.control.emit('keydown',{key:'F5',code:'F5'});assert.equal(sent.length,count,'Destroyed physical handlers retained input');
console.log('Optional surface renderer: focus, raw pointer/click and shortcut routing passed; no browser qualification');
