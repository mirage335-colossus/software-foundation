import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {resolve} from 'node:path';
const {Renderer,identity}=await import(pathToFileURL(resolve(process.argv[2])));

// Realistic capture/bubble propagation keeps overlapping logical widgets as
// DOM siblings. Context routing must follow shared declarations, while labels
// retain their native hit testing, help and selection behavior.
class Element {
  constructor(document,tag='div'){
    this.ownerDocument=document;this.tagName=tag.toUpperCase();this.children=[];this.dataset={};this.attributes={};this.events=new Map();
    this.style={setProperty:(name,value)=>this.style[name]=value};this.scrollLeft=0;this.scrollTop=0;this.value='';
  }
  append(child){child.remove();this.children.push(child);child.parent=this;}
  insertBefore(child,before){child.remove();const index=before?this.children.indexOf(before):this.children.length;this.children.splice(index,0,child);child.parent=this;}
  remove(){if(this.parent)this.parent.children=this.parent.children.filter(value=>value!==this);this.parent=null;}
  replaceChildren(){for(const child of [...this.children])child.remove();}
  setAttribute(name,value){this.attributes[name]=value;}
  addEventListener(kind,callback,options){const values=this.events.get(kind)||[];values.push({callback,capture:options===true||options?.capture===true});this.events.set(kind,values);}
  removeEventListener(kind,callback){this.events.set(kind,(this.events.get(kind)||[]).filter(value=>value.callback!==callback));}
  getBoundingClientRect(){return {left:10,top:20};}
  closest(selector){for(let node=this;node;node=node.parent)if(selector==='.widget'&&node.className?.split(' ').includes('widget'))return node;return null;}
  setSelectionRange(start,end,direction){this.selectionStart=start;this.selectionEnd=end;this.selectionDirection=direction;}
  focus(){this.ownerDocument.activeElement=this;}
  blur(){this.ownerDocument.activeElement=null;}
  emit(kind,values={}){
    let stopped=false,immediate=false;
    const event={target:this,clientX:50,clientY:50,ctrlKey:false,shiftKey:false,altKey:false,defaultPrevented:false,
      preventDefault(){this.defaultPrevented=true;},stopPropagation(){stopped=true;},stopImmediatePropagation(){stopped=true;immediate=true;},...values};
    const path=[];for(let node=this;node;node=node.parent)path.push(node);
    const invoke=(node,capture)=>{for(const value of node.events.get(kind)||[])if(value.capture===capture&&!immediate)value.callback(event);};
    for(const node of [...path].reverse()){invoke(node,true);if(stopped)return event;}
    for(const node of path){invoke(node,false);if(stopped)break;}
    return event;
  }
}
const font={size:14,bold:false,tone:0};
const widget=(id,kind=7,values={})=>({key:{id,generation:'1'},kind,parent:'',page:'',bounds:[0,0,100,80],clip:[0,0,100,80],
  visible:true,enabled:true,inModal:true,label:'',text:'Decoration',help:'Native label help',accessibleName:'',placeholder:'',font,wrap:false,
  pointerInput:false,contextInput:kind===7,actions:[],options:[],records:[],contentSize:[100,80],scroll:[0,0],scrollRevision:'0',
  multiline:false,readOnly:false,masked:false,selection:[0,0],submit:0,rowHeight:20,...values});
const view=widgets=>({title:'Context routing fixture',palette:{},width:300,height:200,pages:[],widgets,focus:null,popup:null,
  measurements:[],keyBindings:[],closed:false});
function setup(widgets){
  const document=new Element(null);document.ownerDocument=document;document.defaultView=new Element(document);
  document.createElement=tag=>new Element(document,tag);document.body=new Element(document,'body');document.body.parent=document;
  const root=new Element(document),pages=new Element(document);document.body.append(root);document.body.append(pages);const sent=[];
  const renderer=new Renderer(root,pages,operation=>{sent.push(operation);return Promise.resolve({});},document);
  const snapshot=view(widgets);renderer.acceptSnapshot(snapshot);renderer.render(snapshot);
  const entry=id=>renderer.nodes.get(identity(widgets.find(value=>value.key.id===id).key));
  return {renderer,root,sent,snapshot,entry,emit:(id,values)=>entry(id).control.emit('contextmenu',values)};
}
function context(result,event,key,values={}){
  assert.equal(event.defaultPrevented,true,'shared context intent must own the native event');
  assert.deepEqual(result.sent,[{type:'pointer',key,kind:'context',pointerId:'0',x:40,y:30,wheelX:0,wheelY:0,
    control:false,shift:false,alt:false,...values}],'one context gesture must reach the current shared target');
}
function unchanged(result,event){assert.equal(result.sent.length,0,'unavailable or covered context input must not dispatch');}
const surface=widget('surface'),label=widget('label',1);
{
  const result=setup([surface]);context(result,result.emit('surface'),surface.key);result.renderer.destroy();
}
{
  const result=setup([surface,label]);
  context(result,result.emit('label',{ctrlKey:true,shiftKey:true,altKey:true}),surface.key,{control:true,shift:true,alt:true});
  assert.equal(result.entry('label').node.title,label.help,'inert decoration must retain native help');
  assert.equal(result.entry('label').node.style.pointerEvents,undefined,'context routing must not disable native label hit testing');
  assert.equal(result.entry('label').control.emit('copy').defaultPrevented,false,'ordinary label selection/copy must remain native');
  result.renderer.destroy();
}
// Shared clip coordinates decide whether an interactive overlay blocks. The
// half-open right/bottom edges do not steal input from a surface underneath.
for(const [clip,blocked] of [[[0,0,100,80],true],[[0,0,30,20],false],[[0,0,40,80],false],[[0,0,100,30],false]]){
  const cover=widget('cover',2,{clip}),result=setup([surface,cover,label]),event=result.emit('label');
  if(blocked){unchanged(result,event);assert.equal(event.defaultPrevented,false,'ordinary live controls retain their native context menu');}
  else context(result,event,surface.key);
  result.renderer.destroy();
}
for(const kind of [0,1,7]){
  const inert=widget('inert',kind,{contextInput:false}),result=setup([surface,inert]);
  context(result,result.emit('inert'),surface.key);result.renderer.destroy();
}
for(const cover of [widget('raw',1,{pointerInput:true}),widget('editor',5),widget('context-label',1,{contextInput:true})]){
  const result=setup([surface,cover,label]),event=result.emit('label');
  if(cover.contextInput)context(result,event,cover.key);else unchanged(result,event);
  result.renderer.destroy();
}
for(const values of [{visible:false},{enabled:false},{inModal:false},{clip:[120,120,20,20]}]){
  const result=setup([surface,label]);result.renderer.acceptSnapshot(view([{...surface,...values},label]));
  unchanged(result,result.emit('label'));result.renderer.destroy();
}
for(const values of [{visible:false},{enabled:false},{inModal:false}]){
  const cover=widget('cover',2,values),result=setup([surface,cover,label]);
  context(result,result.emit('label'),surface.key);result.renderer.destroy();
}
// Accepted declarations take effect before DOM painting. Removed generations
// cannot be reinterpreted as replacement controls, nor can unpainted live
// overlays be skipped to reach the old surface below.
{
  const result=setup([surface,label]);result.renderer.acceptSnapshot(view([{...surface,contextInput:false},label]));
  unchanged(result,result.emit('label'));result.renderer.destroy();
}
{
  const result=setup([surface,label]),replacement={...surface,key:{...surface.key,generation:'2'}};
  result.renderer.acceptSnapshot(view([replacement,label]));unchanged(result,result.emit('surface'));unchanged(result,result.emit('label'));
  result.renderer.render(view([replacement,label]));result.sent.length=0;
  const event=result.renderer.nodes.get(identity(replacement.key)).control.emit('contextmenu');context(result,event,replacement.key);result.renderer.destroy();
}
{
  const result=setup([surface,label]);result.renderer.acceptSnapshot(view([surface]));
  unchanged(result,result.emit('label'));result.renderer.destroy();
}
{
  const result=setup([surface,label]);result.renderer.acceptSnapshot(view([surface,widget('new-cover',2),label]));
  unchanged(result,result.emit('label'));result.renderer.destroy();
}
for(const guard of ['popup','gesture','closed','prevented']){
  const result=setup([surface,label]);
  if(guard==='popup')result.renderer.acceptSnapshot({...result.snapshot,popup:{key:surface.key}});
  if(guard==='gesture')result.renderer.activePointers.add(()=>{});
  if(guard==='closed')result.renderer.acceptSnapshot({...result.snapshot,closed:true});
  unchanged(result,result.emit('label',guard==='prevented'?{defaultPrevented:true}:{}));result.renderer.destroy();
}
for(const values of [{clientX:NaN},{clientY:Infinity}]){
  const result=setup([surface,label]);unchanged(result,result.emit('label',values));result.renderer.destroy();
}
for(const decorated of [false,true]){
  const legacy=widget('legacy',7,{contextInput:false,actions:[{id:'inspect',label:'Inspect',enabled:true}]}),result=setup(decorated?[legacy,label]:[legacy]);
  const event=result.emit(decorated?'label':'legacy');assert.equal(event.defaultPrevented,true);
  assert.deepEqual(result.sent,[{type:'popupOpen',key:legacy.key}],'ordinary declared bitmap actions must retain their popup');result.renderer.destroy();
}
console.log('Browser context routing through inert decorations, shared clips/topmost controls, current generations, modal/gesture guards and legacy popups passed');
