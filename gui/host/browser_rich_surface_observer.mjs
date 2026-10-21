// Read-only observation of the existing renderer and its native document
// endpoint. This owns no transport, input, page evaluator or second document.
export function createRichSurfaceObserver({generation,documentEndpoint,resolveCanvas}) {
  if(typeof generation!=='string'||!/^[0-9a-f]{64}$/.test(generation)||
      !documentEndpoint||typeof documentEndpoint.state!=='function'||typeof documentEndpoint.submit!=='function'||
      typeof resolveCanvas!=='function')throw Error('Invalid rich surface observer binding');
  const copy=value=>value===undefined?null:JSON.parse(JSON.stringify(value));
  const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
  const rect=value=>Array.isArray(value)?{x:value[0],y:value[1],width:value[2],height:value[3]}:copy(value);
  const finiteRect=value=>value&&['x','y','width','height'].every(key=>typeof value[key]==='number'&&Number.isFinite(value[key])&&Math.abs(value[key])<=1000000)&&value.width>0&&value.height>0;
  let closed=false,refreshing=false,accepted=null,drawn=null;
  const image=value=>{
    const widgets=value?.widgets?.filter(widget=>widget.key?.id==='engine.frame');
    if(widgets?.length!==1)return null;
    const widget=widgets[0];
    if(!widget.image||!widget.visible||!widget.enabled||!widget.inModal)return null;
    const bitmap={source:widget.image.source,revision:widget.image.revision,width:widget.image.width,height:widget.image.height};
    return {key:copy(widget.key),bounds:rect(widget.bounds),clip:rect(widget.clip),bitmap};
  };
  const read=()=>{
    let presentation=null;
    const current=accepted?.image,p=accepted?.surface?.presentation;
    if(!closed&&current&&drawn&&p&&same(p.identity.owner,current.key)){
      const node=resolveCanvas(current.key),r=node?.getBoundingClientRect?.();
      const canvas=r?{x:r.left,y:r.top,width:r.width,height:r.height}:null;
      const rendered=same(current,drawn.image)&&node?.width===current.bitmap.width&&node?.height===current.bitmap.height;
      presentation={snapshotRevision:accepted.revision,renderedRevision:drawn.revision,identity:copy(p.identity),
        available:Boolean(p.available&&!accepted.closed&&!accepted.surface.serviceActive&&rendered&&finiteRect(canvas)),
        bounds:rect(p.bounds),clip:rect(p.clip),displayScale:p.displayScale,bitmap:copy(current.bitmap),canvas};
    }
    return copy({protocol:'foundation-rich-surface-observer-v1',frontendGeneration:generation,closed,presentation,
      document:closed?null:documentEndpoint.state()});
  };
  const api=Object.freeze({read,async observeDocument(){
    if(closed)throw Error('Rich surface observer closed');
    if(refreshing)throw Error('Rich document observation is active');
    refreshing=true;
    try{
      // Only the existing read-only Observe intent is exposed. In particular,
      // Begin, editing, native leases, ACK and replay are not observer inputs.
      const result=await documentEndpoint.submit({kind:'observe'});
      if(closed)throw Error('Rich surface observer closed');
      const state=documentEndpoint.state();
      if(result.outcome!=='completed'||!state?.available||!result.observation||result.observation!==state.observation)
        throw Error('Native document observation did not complete');
      return read();
    }finally{refreshing=false;}
  }});
  return Object.freeze({api,
    accept(snapshot,surface){if(!closed)accepted={revision:snapshot.revision,closed:snapshot.closed,image:image(snapshot),surface:copy(surface)};},
    // Called after Renderer.render returns, including the synchronous canvas
    // putImageData. Channel stateAck can precede this animation-frame work.
    presented(snapshot){if(!closed)drawn={revision:snapshot.revision,image:image(snapshot)};},
    close(){closed=true;accepted=null;drawn=null;}
  });
}
