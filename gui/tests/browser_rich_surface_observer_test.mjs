import assert from 'node:assert/strict';
import test from 'node:test';
import {createRichSurfaceObserver} from '../host/browser_rich_surface_observer.mjs';

const clone=value=>JSON.parse(JSON.stringify(value));
function fixture(){
  const key={id:'engine.frame',generation:'2'},identity={owner:key,presentationRevision:'7',generation:'3',epoch:'4',context:'5'};
  const rectangle={x:0,y:0,width:800,height:600};
  const snapshot={revision:'7',closed:false,widgets:[{key,visible:true,enabled:true,inModal:true,bounds:[0,0,800,600],clip:[0,0,800,600],image:{source:'owned-engine-frame',revision:'11',width:800,height:600}}]};
  const surface={serviceActive:false,presentation:{identity,available:true,bounds:rectangle,clip:rectangle,displayScale:1}};
  const canvas={width:800,height:600,getBoundingClientRect:()=>({left:12,top:20,width:400,height:300})};
  let state={available:true,observation:'17',document:{body:{snapshot:{nodes:[{text:'Original'}]}}}},calls=[];
  const endpoint={state:()=>state,async submit(intent){calls.push(clone(intent));state={...state,observation:'18'};return {outcome:'completed',observation:'18'};}};
  const observer=createRichSurfaceObserver({generation:'a'.repeat(64),documentEndpoint:endpoint,resolveCanvas:k=>JSON.stringify(k)===JSON.stringify(key)?canvas:null});
  return {observer,snapshot,surface,canvas,endpoint,calls,state:()=>state};
}
test('acceptance does not claim canvas application before rendering',()=>{
  const f=fixture();f.observer.accept(f.snapshot,f.surface);
  assert.equal(f.observer.api.read().presentation,null);
  f.observer.presented(f.snapshot);const read=f.observer.api.read();
  assert.equal(read.presentation.available,true);assert.equal(read.presentation.renderedRevision,'7');
  assert.deepEqual(read.presentation.canvas,{x:12,y:20,width:400,height:300});
  assert.deepEqual(Object.keys(f.observer.api).sort(),['observeDocument','read']);
});
test('a newer accepted image stays unavailable until the real render callback',()=>{
  const f=fixture();f.observer.accept(f.snapshot,f.surface);f.observer.presented(f.snapshot);
  const next=clone(f.snapshot);next.revision='8';next.widgets[0].image.revision='12';
  const surface=clone(f.surface);surface.presentation.identity.presentationRevision='8';
  f.observer.accept(next,surface);assert.equal(f.observer.api.read().presentation.available,false);
  f.observer.presented(next);assert.equal(f.observer.api.read().presentation.available,true);
  assert.equal(f.observer.api.read().presentation.bitmap.revision,'12');
});
test('fresh metadata can retain the same actually drawn image without inventing a render',()=>{
  const f=fixture();f.observer.accept(f.snapshot,f.surface);f.observer.presented(f.snapshot);
  const next=clone(f.snapshot);next.revision='8';const surface=clone(f.surface);surface.presentation.identity.presentationRevision='8';
  f.observer.accept(next,surface);const read=f.observer.api.read();
  assert.equal(read.presentation.available,true);assert.equal(read.presentation.snapshotRevision,'8');
  assert.equal(read.presentation.renderedRevision,'7');
});
test('retirement, clipping changes and native service holds do not preserve input availability',()=>{
  for(const change of [f=>{f.surface.presentation.available=false;},f=>{f.surface.serviceActive=true;},f=>{f.snapshot.closed=true;},f=>{f.snapshot.widgets[0].bounds[2]=400;},f=>{f.snapshot.widgets[0].key.generation='99';},f=>{f.canvas.width=799;}]){
    const f=fixture();f.observer.accept(f.snapshot,f.surface);f.observer.presented(f.snapshot);change(f);f.observer.accept(f.snapshot,f.surface);
    assert.notEqual(f.observer.api.read().presentation?.available,true);
  }
});
test('the public API returns independent copies, including native content',()=>{
  const f=fixture();f.observer.accept(f.snapshot,f.surface);f.observer.presented(f.snapshot);
  const read=f.observer.api.read();read.presentation.identity.owner.id='foreign';read.document.document.body.snapshot.nodes[0].text='Changed';
  assert.equal(f.observer.api.read().presentation.identity.owner.id,'engine.frame');
  assert.equal(f.state().document.body.snapshot.nodes[0].text,'Original');
});
test('fresh document observation uses only the existing serialized Observe request',async()=>{
  const f=fixture();const read=await f.observer.api.observeDocument();
  assert.deepEqual(f.calls,[{kind:'observe'}]);assert.equal(read.document.observation,'18');
  f.endpoint.submit=async()=>({outcome:'unknown',observation:'18'});
  await assert.rejects(f.observer.api.observeDocument(),/did not complete/);
});
test('close makes old publications unavailable and prevents late observation success',async()=>{
  const f=fixture();let complete;
  f.endpoint.submit=()=>new Promise(resolve=>{complete=resolve;});
  const pending=f.observer.api.observeDocument();await assert.rejects(f.observer.api.observeDocument(),/active/);
  f.observer.close();complete({outcome:'completed',observation:'17'});
  await assert.rejects(pending,/closed/);assert.equal(f.observer.api.read().closed,true);
  assert.equal(f.observer.api.read().document,null);assert.equal(f.observer.api.read().presentation,null);
  await assert.rejects(f.observer.api.observeDocument(),/closed/);
});
