import assert from 'node:assert/strict';
import {MessageChannel} from 'node:worker_threads';
import {pathToFileURL} from 'node:url';
const mouseProfile=process.argv[3]==='mouse_v1',features=mouseProfile?'33':'97';
class Element {
  constructor(document,tag='div'){this.ownerDocument=document;this.tagName=tag.toUpperCase();this.children=[];this.dataset={};this.attributes={};this.events=new Map();this.style={setProperty:(key,value)=>this.style[key]=value};this.scrollLeft=0;this.scrollTop=0;this.value='';this.captures=new Set();}
  append(child){child.remove();this.children.push(child);child.parent=this;}
  insertBefore(child,before){child.remove();const index=before?this.children.indexOf(before):this.children.length;this.children.splice(index,0,child);child.parent=this;}
  remove(){if(this.parent)this.parent.children=this.parent.children.filter(child=>child!==this);this.parent=null;}
  replaceChildren(){for(const child of [...this.children])child.remove();}
  setAttribute(key,value){this.attributes[key]=value;}
  addEventListener(type,callback,options){const list=this.events.get(type)||[];list.push({callback,capture:options===true||!!options?.capture});this.events.set(type,list);}
  removeEventListener(type,callback){this.events.set(type,(this.events.get(type)||[]).filter(value=>value.callback!==callback));}
  getBoundingClientRect(){return {left:0,top:0,width:100,height:80};}
  contains(value){for(let node=value;node;node=node.parent)if(node===this)return true;return false;}
  closest(selector){for(let node=this;node;node=node.parent)if(selector==='.widget'&&node.className?.split(' ').includes('widget'))return node;return null;}
  focus(){this.ownerDocument.activeElement=this;this.emit('focusin');this.emit('focus');}
  blur(){this.ownerDocument.activeElement=null;this.emit('focusout');}
  setPointerCapture(pointer){this.captures.add(pointer);}
  releasePointerCapture(pointer){this.captures.delete(pointer);this.emit('lostpointercapture',{pointerId:pointer});}
  emit(type,values={}){
    const event={type,target:this,clientX:5,clientY:5,pointerId:1,button:0,buttons:0,detail:1,key:'',code:'',location:0,repeat:false,defaultPrevented:false,stopped:false,
      preventDefault(){this.defaultPrevented=true;},stopImmediatePropagation(){this.stopped=true;},stopPropagation(){this.stopped=true;},...values};
    const path=[];for(let node=this;node;node=node.parent)path.push(node);
    for(const node of [...path].reverse())for(const entry of node.events.get(type)||[])if(entry.capture&&!event.stopped)entry.callback(event);
    for(const node of path)for(const entry of node.events.get(type)||[])if(!entry.capture&&!event.stopped)entry.callback(event);
    return event;
  }
}
let nextGeneration=0;
function environment(){
  const generation='frame-'+(++nextGeneration),document=new Element(null);document.ownerDocument=document;document.createElement=tag=>new Element(document,tag);document.visibilityState='visible';
  document.body=new Element(document,'body');document.body.parent=document;
  const root=new Element(document),pages=new Element(document,'nav');root.append(pages);document.body.append(root);
  document.querySelector=selector=>selector.startsWith('meta[')?{content:generation}:selector==='#stage'?root:selector==='#pages'?pages:null;
  document.querySelectorAll=()=>[];
  const host=new Element(document);host.document=document;document.defaultView=host;host.PointerEvent=class{};host.MessageChannel=MessageChannel;
  let nextFrame=0;const frames=new Map();host.requestAnimationFrame=callback=>{frames.set(++nextFrame,callback);return nextFrame;};host.cancelAnimationFrame=id=>frames.delete(id);
  host.setTimeout=setTimeout;host.clearTimeout=clearTimeout;const announced=[];
  host.parent={postMessage(message,origin,ports){announced.push({message,port:ports[0]});}};
  host.emit=(type,values={})=>{for(const entry of [...(host.events.get(type)||[])])entry.callback({type,...values});};
  const received=[],acknowledgedPaint=[];let port=null,stateRevision=0;
  const attach=()=>{assert.equal(announced.length,1);port=announced[0].port;port.onmessage=event=>{received.push(event.data);if(event.data.type==='stateAck'){const painted=root.children.find(value=>value.dataset.key);acknowledgedPaint.push({revision:event.data.revision,owner:painted?.dataset.key,left:painted?.style.left});}};port.start();port.postMessage({protocol:'foundation-renderer-v1',type:'connect',generation});};
  const state=(snapshot,surface,hasSurface=true,values={})=>{const packet={protocol:'foundation-renderer-v1',type:'state',generation,revision:String(++stateRevision),snapshot,barrier:false,cancelPointers:false,...values};if(hasSurface)packet.surface=surface;port.postMessage(packet);return String(stateRevision);};
  const result=(id,ok=true,error='')=>port.postMessage({protocol:'foundation-renderer-v1',type:'result',generation,id,ok,error});
  return {host,document,root,pages,announced,received,acknowledgedPaint,frames,attach,state,result,requests:()=>received.filter(value=>value.type==='request'),close(){host.emit('pagehide');port?.close();}};
}
const font={size:14,bold:false,tone:0};
const widget=(generation='1',x=0)=>({key:{id:'surface',generation},kind:2,parent:'',page:'',bounds:[x,0,100,80],clip:[x,0,100,80],visible:true,enabled:true,inModal:true,label:'Surface',text:'',help:'',accessibleName:'',placeholder:'',font,wrap:false,pointerInput:false,contextInput:false,actions:[],options:[],records:[],contentSize:[100,80],scroll:[0,0],scrollRevision:'0',multiline:false,readOnly:false,masked:false,selection:[0,0],submit:0,rowHeight:20});
const snapshot=(revision='1',generation='1',x=0)=>({revision,title:'Surface frame fixture',palette:{},width:300,height:200,scale:1,pages:[],activePage:null,widgets:[widget(generation,x)],focus:null,popup:null,measurements:[],keyBindings:[],closed:false});
const surface=(view,values={})=>({version:1,capabilities:{version:1,supported:features,limits:{textBytes:65536,clipboardBytes:65536,popupItems:1024,popupTextBytes:65536,captureRules:64,heldKeys:64,popupDepth:8}},
  presentation:{identity:{owner:view.widgets[0].key,presentationRevision:view.revision,generation:'7',epoch:'1',context:view.widgets[0].key.generation},required:features,bounds:view.widgets[0].bounds,clip:view.widgets[0].clip,displayScale:1,available:true,keys:{fallback:'capture',rules:[]},editor:null,clipboard:null,popup:null},focused:false,active:true,composition:null,lastSequence:'0',serviceActive:false,...values});
const flush=async()=>{for(let n=0;n<8;n++)await new Promise(resolve=>setImmediate(resolve));};
const control=env=>env.root.children.find(value=>value.dataset.key)?.children[0];
const automatic=environment();
Object.assign(globalThis,{document:automatic.document,parent:automatic.host.parent,MessageChannel,addEventListener:automatic.host.addEventListener.bind(automatic.host),removeEventListener:automatic.host.removeEventListener.bind(automatic.host),requestAnimationFrame:automatic.host.requestAnimationFrame,cancelAnimationFrame:automatic.host.cancelAnimationFrame});
const {startRendererFrame}=await import(pathToFileURL(process.argv[2]));
{
  const env=automatic;env.attach();await flush();assert(env.received.some(value=>value.type==='bound'));
  env.state(snapshot(),null);await flush();assert.equal(env.requests().length,1);assert.equal(env.requests()[0].operation.type,'surfaceConnect');
  if(mouseProfile){assert.equal(env.requests()[0].operation.supported,'33','Missing native classifier falsely advertised mouse');assert(!Object.hasOwn(env.requests()[0].operation,'mouseInputVersion'));}
  const old=control(env);const before=env.requests().length;old.emit('keydown',{key:'F5',code:'F5'});assert.equal(env.requests().length,before,'Raw input queued before handshake');
  const first=snapshot();env.state(first,surface(first));await flush();env.result('1');await flush();
  old.focus();await flush();assert.equal(env.requests().at(-1).operation.input.kind,'focus');
  env.state(first,surface(first,{focused:true,lastSequence:'1'}));await flush();env.result('2');await flush();
  const event=old.emit('keydown',{key:'F5',code:'F5'});assert(event.defaultPrevented,'Accepted capture decision was not synchronous');await flush();assert.equal(env.requests().at(-1).operation.input.kind,'key');
  const second=snapshot('2');env.state(second,surface(second,{focused:true,lastSequence:'1'}));await flush();env.result('3',false,'Surface identity was replaced');await flush();
  assert(!Object.hasOwn(env.root.attributes,'inert'),'Ordinary stale input destroyed the frame');
  assert(env.frames.size>0,'Same-geometry pixel replacement should remain paint-coalescible');
  const moved=snapshot('3','2',120),revision=env.state(moved,surface(moved));await flush();
  const current=control(env);assert.notEqual(current,old,'Physical owner generation was not painted before acknowledgment');
  assert.equal(current.parent.style.left,'120px','Accepted geometry was left behind a deferred paint');
  assert.deepEqual(env.acknowledgedPaint.find(value=>value.revision===revision),{revision,owner:JSON.stringify(['surface','2']),left:'120px'},'State acknowledgment preceded painting the new physical ownership basis');
  const count=env.requests().length;old.emit('pointerdown',{buttons:1});await flush();assert.equal(env.requests().length,count,'Removed painted DOM granted replacement owner input');
  env.close();assert(Object.hasOwn(env.root.attributes,'inert'));
}
{
  const env=environment(),controller=startRendererFrame(env.host);env.attach();await flush();env.state(snapshot(),null);await flush();assert.equal(env.requests().length,1);
  controller.close();assert(Object.hasOwn(env.root.attributes,'inert'));const count=env.requests().length;
  const view=snapshot();env.state(view,surface(view));env.result('1');await flush();
  assert.equal(env.requests().length,count,'Late handshake work revived closed frame');
  assert.equal((env.document.events.get('keydown')||[]).length,0,'Closed frame retained physical/global key listeners');env.close();
}
{
  const env=environment();startRendererFrame(env.host);env.attach();await flush();env.state(snapshot(),null,false);await flush();
  assert.equal(env.requests().length,0,'Legacy first state started a surface handshake');
  env.state(snapshot(),null,true);await flush();assert(Object.hasOwn(env.root.attributes,'inert'),'Legacy profile silently upgraded');env.close();
}
{
  const env=environment();startRendererFrame(env.host);env.attach();await flush();env.state(snapshot(),null,true,{cancelPointers:true});await flush();
  assert.equal(env.requests().length,0,'Owned service did not defer capability handshake');
  env.state(snapshot(),null);await flush();assert.equal(env.requests().length,1);assert.equal(env.requests()[0].operation.type,'surfaceConnect');env.close();
}
console.log('Rich frame profile lock, receipt barrier, stale input, painted ownership, owned service and late teardown checks passed; no browser qualification');
