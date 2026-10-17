// Generic owned-value document transport. Native authority and publication/ACK
// decisions remain in the application-owned C++ broker.
const encoder=new TextEncoder(),maximum=(1n<<64n)-1n;
const invalid=message=>{throw Error(message||'Invalid browser document packet');};
const stale=message=>{const error=Error(message);error.stale=true;throw error;};
const enumValue=(value,values)=>{if(!values.includes(value))invalid();};
const uint=(value,max=0xffffffff)=>{if(!Number.isSafeInteger(value)||value<0||value>max)invalid();};
const decimal=(value,zero=false)=>{if(typeof value!=='string'||!/^(0|[1-9][0-9]{0,19})$/.test(value)||BigInt(value)>maximum||!zero&&value==='0')invalid();return value;};
const bool=value=>{if(typeof value!=='boolean')invalid();};
const scalar=(value,units=2048)=>{if(typeof value!=='string'||value.length>units)invalid();for(const c of value){const n=c.codePointAt(0);if(!n||n>=0xd800&&n<=0xdfff)invalid();}};
const shape=(value,names)=>{if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).length!==names.length||names.some(key=>!Object.hasOwn(value,key)))invalid();};
const list=(value,max,fn)=>{if(!Array.isArray(value)||value.length>max)invalid();for(const item of value)fn(item);};
const nullable=(value,fn)=>{if(value!==null)fn(value);};
const copy=(value,maximumBytes=33554432)=>{
  const budget={nodes:0,bytes:0};
  const take=(item,depth=0)=>{
    if(++budget.nodes>131072||depth>32)invalid('Document packet structure limit');
    if(item===null||typeof item==='boolean')return item;
    if(typeof item==='number'){if(!Number.isFinite(item))invalid();return item;}
    if(typeof item==='string'){budget.bytes+=encoder.encode(item).length;if(budget.bytes>maximumBytes)invalid('Document packet byte limit');return item;}
    if(!item||typeof item!=='object')invalid();
    const array=Array.isArray(item),prototype=Object.getPrototypeOf(item);
    if(array?prototype!==Array.prototype:prototype!==Object.prototype&&prototype!==null)invalid();
    const out=array?[]:{};if(array&&item.length>4096)invalid();
    for(const key of Reflect.ownKeys(item)){
      if(array&&key==='length')continue;const d=Object.getOwnPropertyDescriptor(item,key);
      if(typeof key!=='string'||key.length>64||!d?.enumerable||!Object.hasOwn(d,'value')||array&&(!/^(0|[1-9][0-9]*)$/.test(key)||Number(key)>=item.length))invalid();
      Object.defineProperty(out,key,{value:take(d.value,depth+1),enumerable:true});
    }
    if(array&&Object.keys(out).length!==item.length)invalid();return Object.freeze(out);
  };
  const result=take(value);if(encoder.encode(JSON.stringify(result)).length>maximumBytes)invalid('Document packet byte limit');return result;
};
const canonical=value=>value===null||typeof value!=='object'?JSON.stringify(value):Array.isArray(value)?'['+value.map(canonical).join(',')+']':'{'+Object.keys(value).sort().map(key=>JSON.stringify(key)+':'+canonical(value[key])).join(',')+'}';
const kinds=['text','number','textarea','checkbox','select_one','select_many','secure_readonly','unsupported'];
const phases=['idle','queued','waitingNative','waitingPublication','waitingAck','waitingTake','terminal'];
const draftPhases=['editing','pending','stale','unknown','unavailable','closed'];
const admissions=['accepted','busy','unavailable','stale','invalid','limit','closed'];
const version=v=>{shape(v,['generation','epoch','revision']);for(const key of Object.keys(v))decimal(v[key]);};
const selection=v=>{shape(v,['anchor','caret']);uint(v.anchor,8192);uint(v.caret,8192);};
const boundary=(value,at)=>{const bytes=encoder.encode(value);return at<=bytes.length&&(at===bytes.length||(bytes[at]&192)!==128);};
const draft=v=>{
  shape(v,['id','kind','phase','text','selection','checked','dirty','applyQueued','option']);decimal(v.id);enumValue(v.kind,kinds);enumValue(v.phase,draftPhases);scalar(v.text);selection(v.selection);
  if(!boundary(v.text,v.selection.anchor)||!boundary(v.text,v.selection.caret))invalid();for(const key of ['checked','dirty','applyQueued'])bool(v[key]);
  nullable(v.option,o=>{shape(o,['node','selected']);decimal(o.node);bool(o.selected);});
};
const point=v=>{shape(v,['node','utf16Offset']);decimal(v.node);uint(v.utf16Offset);};
const documentSelection=v=>{shape(v,['anchor','focus']);point(v.anchor);point(v.focus);};
const nativePoint=v=>{shape(v,['node','offset','kind']);decimal(v.node);uint(v.offset);enumValue(v.kind,['text_utf16','element_child_index']);};
const rect=v=>{shape(v,['x','y','width','height']);for(const key of Object.keys(v))if(typeof v[key]!=='number'||!Number.isFinite(v[key]))invalid();if(v.width<0||v.height<0)invalid();};
const snapshot=v=>{
  shape(v,['version','nodes','activeNode','selection','truncated']);version(v.version);bool(v.truncated);nullable(v.activeNode,decimal);nullable(v.selection,documentSelection);
  const ids=new Set();list(v.nodes,2048,n=>{shape(n,['id','parent','kind','tag','text','name','value','href','whiteSpace','omitted','masked','disabled','editable']);decimal(n.id);decimal(n.parent,true);if(ids.has(n.id))invalid();ids.add(n.id);enumValue(n.kind,['element','text']);enumValue(n.whiteSpace,['normal','pre','pre_wrap']);for(const key of ['tag','text','name','value','href'])scalar(n[key]);for(const key of ['omitted','masked','disabled','editable'])bool(n[key]);});
};
const range=v=>{shape(v,['start','end','direction']);uint(v.start,2048);uint(v.end,2048);if(v.start>v.end)invalid();enumValue(v.direction,['none','forward','backward']);};
const control=v=>{
  shape(v,['node','kind','nativeType','label','disabled','readOnly','focusable','focused','omitted','complete','capabilities','state','lease']);decimal(v.node);enumValue(v.kind,kinds);scalar(v.nativeType);scalar(v.label);uint(v.capabilities,31);
  for(const key of ['disabled','readOnly','focusable','focused','omitted','complete'])bool(v[key]);
  nullable(v.lease,l=>{shape(l,['captured','node','id']);version(l.captured);decimal(l.node);decimal(l.id);if(l.node!==v.node)invalid();});
  nullable(v.state,s=>{shape(s,['kind','value']);enumValue(s.kind,['text','check','select']);const data=s.value;
    if(s.kind==='text'){shape(data,['value','editingText','selection']);scalar(data.value);scalar(data.editingText);nullable(data.selection,range);}
    else if(s.kind==='check'){shape(data,['checked','indeterminate']);bool(data.checked);bool(data.indeterminate);}
    else{shape(data,['multiple','menuList','options']);bool(data.multiple);bool(data.menuList);list(data.options,2048,o=>{shape(o,['node','label','selected','disabled','omitted']);decimal(o.node);scalar(o.label);for(const key of ['selected','disabled','omitted'])bool(o[key]);});}
  });
  if(v.kind==='secure_readonly'&&(v.state!==null||v.lease!==null||v.capabilities!==0))invalid();
};
const document=v=>{
  shape(v,['protocol','publication','body','forms']);if(v.protocol!==2)invalid();version(v.publication);
  const b=v.body;shape(b,['requestId','epoch','errorCode','snapshot','editorState','metadata','originalSelection','degraded']);decimal(b.requestId,true);decimal(b.epoch,true);scalar(b.errorCode);nullable(b.snapshot,snapshot);
  nullable(b.editorState,e=>{shape(e,['revision','flags']);uint(e.revision);uint(e.flags);});
  list(b.metadata,2048,m=>{shape(m,['node','role','display','whiteSpace','readOnly','checked']);decimal(m.node);for(const key of ['role','display','whiteSpace'])scalar(m[key]);bool(m.readOnly);bool(m.checked);});
  nullable(b.originalSelection,s=>{shape(s,['endpoints','focusRect']);shape(s.endpoints,['anchor','focus']);nativePoint(s.endpoints.anchor);nativePoint(s.endpoints.focus);rect(s.focusRect);});
  shape(b.degraded,['whitespace','elementSelection','truncatedSelection']);for(const key of Object.keys(b.degraded))bool(b.degraded[key]);
  const f=v.forms;shape(f,['protocol','version','controls']);if(f.protocol!==2)invalid();version(f.version);list(f.controls,2048,control);
  const ids=new Set();let options=0;for(const c of f.controls){if(ids.has(c.node))invalid();ids.add(c.node);if(c.state?.kind==='select')options+=c.state.value.options.length;}if(options>2048)invalid();
};
function state(value,snapshotValue=null){
  shape(value,['version','publicationRevision','available','phase','observation','draft','pending','document']);if(value.version!==1)invalid();decimal(value.publicationRevision,true);bool(value.available);enumValue(value.phase,phases);nullable(value.observation,decimal);nullable(value.draft,draft);nullable(value.pending,decimal);nullable(value.document,document);
  if((value.observation===null)!==(value.document===null)||value.publicationRevision==='0'&&(value.observation!==null||value.draft!==null||value.document!==null))invalid();
  if(snapshotValue!==null){
    if(!snapshotValue||typeof snapshotValue!=='object'||![Object.prototype,null].includes(Object.getPrototypeOf(snapshotValue)))invalid();
    const revision=Object.getOwnPropertyDescriptor(snapshotValue,'revision'),closed=Object.getOwnPropertyDescriptor(snapshotValue,'closed');
    if(!revision||!closed||!Object.hasOwn(revision,'value')||!Object.hasOwn(closed,'value'))invalid();decimal(revision.value,true);bool(closed.value);
    if(BigInt(value.publicationRevision)>BigInt(revision.value)||closed.value&&value.available)invalid();
  }
  return value;
}
function completion(v){shape(v,['ticket','outcome','observation','draft','detail']);decimal(v.ticket);enumValue(v.outcome,['completed','rejected','cancelled','unknown']);nullable(v.observation,decimal);nullable(v.draft,draft);scalar(v.detail);}
export function validateDocumentState(value,snapshotValue=null){return state(copy(value),snapshotValue);}
export function validateDocumentOperation(value,current=null){
  const v=copy(value,65536);if(v.type==='documentTake'){shape(v,['type','version','ticket']);if(v.version!==1)invalid();decimal(v.ticket);return v;}
  shape(v,['type','version','intent']);if(v.type!=='documentSubmit'||v.version!==1)invalid();const i=v.intent;
  if(i.kind==='observe')shape(i,['kind']);
  else if(i.kind==='begin'){shape(i,['kind','observation','node']);decimal(i.observation);decimal(i.node);}
  else if(i.kind==='editText'){shape(i,['kind','draft','baseText','text']);decimal(i.draft);scalar(i.baseText);scalar(i.text);}
  else if(i.kind==='selectText'){shape(i,['kind','draft','anchor','caret']);decimal(i.draft);uint(i.anchor,8192);uint(i.caret,8192);}
  else if(i.kind==='setChecked'){shape(i,['kind','draft','checked']);decimal(i.draft);bool(i.checked);}
  else if(i.kind==='setOption'){shape(i,['kind','draft','node','selected']);decimal(i.draft);decimal(i.node);bool(i.selected);}
  else{shape(i,['kind','draft']);enumValue(i.kind,['apply','reload','reapply','cancel','finish']);decimal(i.draft);}
  if(current!==null){current=validateDocumentState(current);if(i.kind==='begin'&&i.observation!==current.observation)stale('Stale document observation');if(Object.hasOwn(i,'draft')&&i.draft!==current.draft?.id)stale('Stale document draft');if(i.kind==='selectText'&&(!boundary(current.draft.text,i.anchor)||!boundary(current.draft.text,i.caret)))invalid('Document selection is not a scalar boundary');}
  return v;
}
export function validateDocumentReply(value,operation=null,sequence=null){
  const v=copy(value);shape(v,['sequence','operation','admission','ticket','completion']);decimal(v.sequence);enumValue(v.operation,['submit','take']);enumValue(v.admission,admissions);nullable(v.ticket,decimal);nullable(v.completion,completion);
  if((v.admission==='accepted')!==(v.ticket!==null)||v.completion!==null&&(v.operation!=='take'||v.completion.ticket!==v.ticket))invalid();
  if(sequence!==null&&v.sequence!==sequence||operation!==null&&v.operation!==(operation.type==='documentTake'?'take':'submit')||operation?.type==='documentTake'&&v.ticket!==null&&v.ticket!==operation.ticket)invalid('Document reply correlation differs');return v;
}

export function createBrowserDocumentEndpoint({send,scheduler=globalThis,maxPolls=32,pollInterval=0,onFailure=()=>{}}={}){
  if(typeof send!=='function'||typeof onFailure!=='function'||!Number.isSafeInteger(maxPolls)||maxPolls<1||maxPolls>32||!Number.isSafeInteger(pollInterval)||pollInterval<0||pollInterval>1000)invalid();
  let closed=false,running=false,current=null,lastSequence=0n,lastKnownCompletion=null;const paired=new Map(),timers=new Map(),inflight=new Set();
  const close=(error=Error('Document endpoint closed'))=>{if(closed)return;closed=true;current=null;lastKnownCompletion=null;paired.clear();for(const reject of inflight)reject(error);inflight.clear();for(const [timer,reject] of timers){scheduler.clearTimeout(timer);reject(error);}timers.clear();};
  const fail=error=>{if(closed)return;close(error);try{onFailure(error);}catch{}};
  const wait=()=>new Promise((resolve,reject)=>{if(closed){reject(Error('Document endpoint closed'));return;}const timer=scheduler.setTimeout(()=>{timers.delete(timer);resolve();},pollInterval);timers.set(timer,reject);});
  const exchange=async operation=>{
    if(closed||!current)invalid('Document endpoint is unavailable');let request;
    try{request=validateDocumentOperation(operation,current);}catch(error){error.admission='invalid';throw error;}
    let cancel;
    const waiting=new Promise((resolve,reject)=>{cancel=reject;inflight.add(reject);try{Promise.resolve(send(request)).then(resolve,reject);}catch(error){reject(error);}});
    let received;try{received=await waiting;}finally{inflight.delete(cancel);}
    const reply=validateDocumentReply(received,request);if(closed)invalid('Document endpoint closed');
    const accepted=paired.get(reply.sequence);if(!accepted||canonical(accepted)!==canonical(reply)||BigInt(reply.sequence)<=lastSequence)invalid('Document reply has no accepted paired state');
    paired.delete(reply.sequence);lastSequence=BigInt(reply.sequence);return reply;
  };
  const refused=reply=>{const error=Error('Document request was '+reply.admission);error.admission=reply.admission;return error;};
  const exclusive=async action=>{if(running){const e=Error('Document endpoint request is active');e.admission='busy';throw e;}running=true;try{return await action();}catch(error){if(!error.admission)fail(error);throw error;}finally{running=false;}};
  return Object.freeze({
    accept(snapshotValue,value,reply=null){
      if(closed)return;try{
        const next=validateDocumentState(value,snapshotValue);
        if(current){if(BigInt(next.publicationRevision)<BigInt(current.publicationRevision))invalid('Document publication revision regressed');if(next.publicationRevision===current.publicationRevision&&canonical([next.observation,next.draft,next.document])!==canonical([current.observation,current.draft,current.document]))invalid('Document content changed without an accepted publication');}
        if(reply!==null){
          const checked=validateDocumentReply(reply);
          if(checked.completion?.outcome==='unknown'){fail(Error('Document consumed outcome is unknown'));return;}
          if(checked.completion!==null){
            if(lastKnownCompletion?.ticket===checked.completion.ticket){
              if(canonical(lastKnownCompletion)!==canonical(checked.completion))invalid('Document completion changed for its validated ticket');
            }else{
              if(canonical([checked.completion.observation,checked.completion.draft])!==canonical([next.observation,next.draft]))invalid('Document completion lost its accepted publication');
              lastKnownCompletion=checked.completion;
            }
          }
          if(BigInt(checked.sequence)>lastSequence){if(paired.has(checked.sequence)&&canonical(paired.get(checked.sequence))!==canonical(checked))invalid('Document paired reply changed');if(!paired.has(checked.sequence)&&paired.size>=128)invalid('Document paired reply inventory limit');paired.set(checked.sequence,checked);}
        }
        current=next;
      }catch(error){fail(error);throw error;}
    },
    state(){return current;},
    submit(intent){return exclusive(async()=>{
      const queued=await exchange({type:'documentSubmit',version:1,intent});if(queued.admission!=='accepted')throw refused(queued);
      for(let n=0;n<maxPolls;++n){const reply=await exchange({type:'documentTake',version:1,ticket:queued.ticket});if(reply.admission!=='accepted')throw refused(reply);if(reply.completion!==null){if(reply.completion.outcome==='unknown')fail(Error('Document consumed outcome is unknown'));return reply.completion;}if(n+1<maxPolls)await wait();}
      invalid('Document completion polling budget exhausted');
    });},
    take(ticket){return exclusive(async()=>{const reply=await exchange({type:'documentTake',version:1,ticket});if(reply.admission!=='accepted')throw refused(reply);if(reply.completion?.outcome==='unknown')fail(Error('Document consumed outcome is unknown'));return reply.completion;});},
    close
  });
}
