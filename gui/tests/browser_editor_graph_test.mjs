// Execute only the selected local renderer graph against explicit DOM/port
// fakes. This is neither a browser qualification nor engine execution.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {pathToFileURL} from 'node:url';
import vm from 'node:vm';

const bundle=await import(pathToFileURL(process.argv[2]).href);
class Target{
  constructor(){this.listeners=new Map();this.style={setProperty(){}};this.children=[];this.dataset={};this.attributes=new Map();}
  addEventListener(name,fn){if(!this.listeners.has(name))this.listeners.set(name,new Set());this.listeners.get(name).add(fn);}
  removeEventListener(name,fn){this.listeners.get(name)?.delete(fn);}
  appendChild(node){this.children.push(node);node.parentNode=this;return node;}
  append(...nodes){for(const node of nodes)this.appendChild(node);}
  replaceChildren(...nodes){this.children=[];this.append(...nodes);}
  setAttribute(name,value){this.attributes.set(name,value);}
  getAttribute(name){return this.attributes.get(name)??null;}
  getBoundingClientRect(){return {left:0,top:0,width:100,height:100};}
  contains(node){return node===this||this.children.includes(node);}
  remove(){}focus(){}blur(){}querySelectorAll(){return [];}
}
test('actual selected bundle constructs editor endpoint and editor surface without evaluating an engine',async()=>{
  const ports=[],ready=[],stage=new Target(),pages=new Target(),body=new Target(),document=new Target();
  document.visibilityState='visible';document.activeElement=stage;document.body=body;document.hasFocus=()=>true;
  document.querySelector=name=>name==='meta[name="foundation-channel"]'?{content:'fixture-editor-generation'}:name==='#stage'?stage:name==='#pages'?pages:null;
  document.createElement=()=>new Target();stage.ownerDocument=document;pages.ownerDocument=document;
  class Port{constructor(){this.sent=[];this.closed=false;}postMessage(value){this.sent.push(value);}start(){}close(){this.closed=true;}}
  const host=new Target();Object.assign(host,{document,console,TextEncoder,TextDecoder,structuredClone,PointerEvent:class{},setTimeout,clearTimeout,queueMicrotask,
    parent:{postMessage(value,origin,transferred){ready.push({value,origin,transferred});}},
    MessageChannel:class{constructor(){this.port1=new Port();this.port2=new Port();ports.push(this);}}});
  const context=vm.createContext(host);vm.runInContext('document.defaultView=globalThis;',context);
  new vm.Script(bundle.CHILD_SCRIPT,{filename:'retained-editor-child.js'}).runInContext(context);
  assert.equal(ready.length,1);assert.equal(ready[0].value.type,'ready');assert.equal(ready[0].origin,'*');
  const channel=ports[0].port1;
  const deliver=value=>channel.onmessage({data:vm.runInContext('JSON.parse('+JSON.stringify(JSON.stringify(value))+')',context),ports:[]});
  deliver({protocol:'foundation-renderer-v1',generation:'fixture-editor-generation',type:'connect'});
  assert.equal(channel.sent[0].type,'bound');
  deliver({protocol:'foundation-renderer-v1',generation:'fixture-editor-generation',type:'state',revision:'1',barrier:true,cancelPointers:false,
    snapshot:{revision:'1',title:'Editor graph',palette:{},width:100,height:100,scale:1,pages:[],activePage:null,widgets:[],measurements:[],keyBindings:[],commands:[],focus:null,popup:null,closed:false},surface:null,editor:null,editorReply:null});
  const connect=channel.sent.find(value=>value.type==='request');assert(connect,'Actual Renderer must construct and connect the selected editor surface');
  // This DOM fake supplies no branded native context-source getter. Its actual
  // listener offer must omit mouse8192 while retaining all six editor bits;
  // claiming the full8255 here would manufacture native browser evidence.
  assert.deepEqual(JSON.parse(JSON.stringify(connect.operation)),{type:'surfaceConnect',version:2,profile:'editor_v1',supported:'63'});
  assert.equal(connect.operation.mouseInputVersion,undefined);
  assert(channel.sent.some(value=>value.type==='stateAck'&&value.revision==='1'),'State accepted before any operation receipt');
  assert.equal(document.title,'Editor graph');
  for(const close of [...host.listeners.get('pagehide')??[]])close();
  await new Promise(resolve=>setImmediate(resolve));assert(channel.closed);
  assert.equal(stage.getAttribute('inert'),'');
});
