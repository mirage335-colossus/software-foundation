// Web-only value facade for foundation::appended::WebServices. This file is
// deliberately separate from the portable guest SDK and from any HTML engine.
export const ServiceStatus=Object.freeze({ok:0,invalid_request:1,unavailable:2,not_found:3,
  unsupported_version:4,schema_mismatch:5,conflict:6,invalid_handle:7,limit_exceeded:8,
  unknown_operation:9,closed:10,internal_error:11,result_available:12,expired:13,uncertain:14});
const HEADER=64,MAX_MESSAGE=1048576,U64_MAX=(1n<<64n)-1n;
const encoder=new TextEncoder(),decoder=new TextDecoder('utf-8',{fatal:true,ignoreBOM:true});
const ByteArray=Uint8Array,typedArray=Object.getPrototypeOf(ByteArray.prototype);
const getter=name=>Object.getOwnPropertyDescriptor(typedArray,name).get;
const bufferOf=getter('buffer'),offsetOf=getter('byteOffset'),lengthOf=getter('byteLength');
const typeOf=Object.getOwnPropertyDescriptor(typedArray,Symbol.toStringTag).get;
const bufferLength=Object.getOwnPropertyDescriptor(ArrayBuffer.prototype,'byteLength').get;
const setBytes=ByteArray.prototype.set;

export class FoundationServiceError extends Error {
  constructor(status,sequence,message=`Foundation service status ${status}`) {
    super(message);this.name='FoundationServiceError';this.status=status;
    if(sequence!==undefined)this.sequence=sequence;
  }
}
const validStatus=value=>Number.isInteger(value)&&value>=0&&value<=ServiceStatus.uncertain;
const u64=value=>typeof value==='bigint'&&value>0n&&value<=U64_MAX;
const integer=(value,min,max)=>Number.isSafeInteger(value)&&value>=min&&value<=max;
function owned(value) {
  try{return typeOf.call(value)==='Uint8Array'&&bufferLength.call(bufferOf.call(value))>=0;}
  catch{return false;}
}
// Typed-array construction copies internal elements, ignoring Buffer.slice,
// subclass species/iterators and shadowed length/buffer properties. Always copy
// only this view, so a small input cannot retain its arbitrarily large backing.
const copy=bytes=>new ByteArray(bytes);
const range=(bytes,start,end=lengthOf.call(bytes))=>
  new ByteArray(bufferOf.call(bytes),offsetOf.call(bytes)+start,end-start);
function equal(left,right) {
  const length=lengthOf.call(left);
  if(length!==lengthOf.call(right))return false;
  for(let i=0;i<length;++i)if(left[i]!==right[i])return false;
  return true;
}
const view=bytes=>new DataView(bufferOf.call(bytes),offsetOf.call(bytes),lengthOf.call(bytes));
const nameValid=name=>typeof name==='string'&&name.length<=128&&/^[a-z][a-z0-9_-]*(?:\.[a-z][a-z0-9_-]*)+$/.test(name);
function scalar(value,bytes) {
  const output=new ByteArray(bytes);
  if(bytes===8)view(output).setBigUint64(0,value,true);else view(output).setUint32(0,value,true);
  return output;
}
function record(fields) {
  const output=new ByteArray(fields.reduce((size,[,,bytes])=>size+8+bytes.length,0));
  let offset=0;
  for(const [id,type,bytes] of fields) {
    const data=view(output);data.setUint16(offset,id,true);output[offset+2]=type;output[offset+3]=1;
    data.setUint32(offset+4,bytes.length,true);setBytes.call(output,bytes,offset+8);offset+=8+bytes.length;
  }
  return output;
}
function request(generation,sequence,handle,operation,payload) {
  const length=lengthOf.call(payload),bytes=new ByteArray(HEADER+length),data=view(bytes);
  data.setUint32(0,bytes.length,true);data.setUint16(4,1,true);data.setUint32(8,1,true);
  data.setBigUint64(16,generation,true);data.setBigUint64(24,sequence,true);
  data.setBigUint64(32,handle,true);data.setUint32(40,operation,true);data.setUint32(44,length,true);
  setBytes.call(bytes,payload,HEADER);return bytes;
}
// Validate canonical optional fields too, including nested values. Unknown
// optional types may be skipped; unknown required fields are schema errors.
function fields(bytes,depth=1) {
  if(depth>8||bytes.length>MAX_MESSAGE)throw Error('Record limit');
  const found=new Map();let offset=0,previous=0;
  while(offset<bytes.length) {
    if(bytes.length-offset<8||found.size===64)throw Error('Record header');
    const data=view(bytes),id=data.getUint16(offset,true),type=bytes[offset+2],flags=bytes[offset+3];
    const length=data.getUint32(offset+4,true);offset+=8;
    if(id<=previous||flags>1||length>bytes.length-offset)throw Error('Record field');
    const value=range(bytes,offset,offset+length),valueData=view(value);
    if((type===1&&length!==4)||([2,3,4].includes(type)&&length!==8)||
       (type===5&&(length!==1||value[0]>1)))throw Error('Record scalar');
    if(type===4) {
      const bits=valueData.getBigUint64(0,true);
      if((bits&0x7ff0000000000000n)===0x7ff0000000000000n&&
         (bits&0xfffffffffffffn)!==0n&&bits!==0x7ff8000000000000n)throw Error('Record NaN');
    }
    if(type===6)decoder.decode(value);
    if(type===8)fields(value,depth+1);
    if(type===9) {
      if(length<4)throw Error('Record list');
      const count=valueData.getUint32(0,true);let cursor=4;
      if(count>1024)throw Error('Record list limit');
      for(let i=0;i<count;++i) {
        if(length-cursor<4)throw Error('Record list header');
        const size=valueData.getUint32(cursor,true);cursor+=4;
        if(size>length-cursor)throw Error('Record list size');
        fields(range(value,cursor,cursor+size),depth+1);cursor+=size;
      }
      if(cursor!==length)throw Error('Record list trailing bytes');
    }
    if((type<1||type>9)&&flags)throw Error('Unknown required type');
    found.set(id,{type,required:flags===1,value});previous=id;offset+=length;
  }
  return found;
}
function descriptor(payload,query,maxPayload) {
  const found=fields(payload),types=[2,6,1,1,7,1];
  for(const [id,field] of found)if((id<=6&&!field.required)||(id>6&&field.required))throw Error('Discovery field policy');
  const values=types.map((type,index)=>{
    const field=found.get(index+1);if(!field||field.type!==type)throw Error('Discovery field type');
    return field.value;
  });
  const handle=view(values[0]).getBigUint64(0,true),name=decoder.decode(values[1]);
  const major=view(values[2]).getUint32(0,true),minor=view(values[3]).getUint32(0,true);
  const schema=values[4],maxReplyBytes=view(values[5]).getUint32(0,true);
  if(!u64(handle)||!nameValid(name)||name!==query.name||major!==query.major||
     minor<query.minMinor||minor>query.maxMinor||schema.length!==32||!schema.some(byte=>byte!==0)||
     (query.schema&&!equal(query.schema,schema))||maxReplyBytes>maxPayload)throw Error('Discovery descriptor');
  const schemaCopy=copy(schema);
  return Object.freeze({handle,name,major,minor,get schema(){return copy(schemaCopy);},maxReplyBytes});
}

/**
 * The injected, internal adapter has three synchronous admission/control methods:
 *   enqueue(owned Uint8Array request, source: 'automatic'|'native'|'module')
 *   cancel(generation: bigint, sequence: bigint)
 *   acknowledge(generation: bigint, throughSequence: bigint)
 * Each returns a numeric ServiceStatus. Only OK admits a new enqueue. enqueue
 * copies/reserves only: no Registry/Module invocation or engine reentry is allowed
 * in these methods. The serialized owner pumps outside its engine callback,
 * takes owned COMPLETION Envelopes after pump returns, and calls receive(bytes).
 * A throw/invalid adapter status leaves admission uncertain; never auto-retry it.
 *
 * Pages use discover() and service.call(), without a native/module routing choice.
 * Promise.sequence is an opaque bigint for explicit cancel/resend. replay(sequence)
 * explicitly resends the saved request and returns its verified outcome Promise,
 * including recovery after the original admission Promise rejected UNCERTAIN.
 * The owner must explicitly acknowledge() the completed prefix to release retention;
 * call it after the engine callback returns, since host ACK may refuse there.
 * Explicit resend/cancel returning EXPIRED retires a request with no live host
 * outcome, including uncertain admission followed by an admitted higher sequence.
 * Before navigation teardown, the owner MUST close the corresponding WebServices
 * queue before any further pump; dispose() only retires this JavaScript document
 * epoch. A successor needs a fresh generation and queue.
 */
export function createFoundationServices(transport,{generation,firstSequence=1n,
  maxMessageBytes=MAX_MESSAGE,maxRetainedCalls=64,maxRetainedBytes=4*MAX_MESSAGE}={}) {
  if(!transport||!['enqueue','cancel','acknowledge'].every(key=>typeof transport[key]==='function')||
     !u64(generation)||!u64(firstSequence)||!integer(maxMessageBytes,HEADER+320,MAX_MESSAGE)||
     !integer(maxRetainedCalls,1,0xffffffff)||!integer(maxRetainedBytes,HEADER,0xffffffff))
    throw new TypeError('Invalid web service transport or limits');
  const methods=Object.fromEntries(['enqueue','cancel','acknowledge'].map(key=>[key,transport[key].bind(transport)]));
  const pending=new Map();let next=firstSequence,retainedBytes=0,acknowledged=0n,closed=false,epoch=0,transportDepth=0;
  const error=(status,sequence,message)=>new FoundationServiceError(status,sequence,message);
  const rejected=(status,message)=>Promise.reject(error(status,undefined,message));
  function settle(entry,sequence,status,value) {
    if(status===ServiceStatus.ok) {entry.resolve?.(value);entry.replay?.resolve(value);}
    else {const failure=error(status,sequence);entry.reject?.(failure);entry.replay?.reject(failure);}
    entry.resolve=null;entry.reject=null;entry.replay=null;
  }
  function invoke(method,...args) {
    ++transportDepth;
    try {const status=methods[method](...args);return validStatus(status)?status:ServiceStatus.uncertain;}
    catch{return ServiceStatus.uncertain;}
    finally{--transportDepth;}
  }
  function begin(handle,operation,payload,maxReplyBytes,query,source='automatic',expectedEpoch=epoch) {
    if(closed||expectedEpoch!==epoch)return rejected(ServiceStatus.closed);
    if(transportDepth)return rejected(ServiceStatus.conflict,'Reentrant web service transport');
    if(!integer(operation,0,0xffffffff)||!owned(payload))return rejected(ServiceStatus.invalid_request);
    const payloadLength=lengthOf.call(payload);
    if(payloadLength>maxMessageBytes-HEADER)return rejected(ServiceStatus.limit_exceeded);
    const reserve=HEADER+payloadLength+HEADER+maxReplyBytes;
    if(next>U64_MAX||pending.size>=maxRetainedCalls||reserve>maxRetainedBytes-retainedBytes)
      return rejected(ServiceStatus.limit_exceeded);
    const sequence=next;let bytes,submission,promise,entry,resolve,reject;
    try {
      bytes=request(generation,sequence,handle,operation,payload);submission=copy(bytes);
      promise=new Promise((yes,no)=>{resolve=yes;reject=no;});
      Object.defineProperty(promise,'sequence',{value:sequence,enumerable:true});
      entry={bytes,handle,operation,maxReplyBytes,query,source,reserve,resolve,reject,
        replay:null,completed:false,completion:null};
      pending.set(sequence,entry);
    }catch{return rejected(ServiceStatus.limit_exceeded,'Could not allocate web service request');}
    ++next;retainedBytes+=reserve;
    const status=invoke('enqueue',submission,source);
    if(closed||expectedEpoch!==epoch)return promise;
    if(status===ServiceStatus.uncertain) {
      reject(error(status,sequence,'Web service admission is uncertain'));entry.resolve=null;entry.reject=null;
    }
    else if(status!==ServiceStatus.ok) {
      pending.delete(sequence);retainedBytes-=reserve;settle(entry,sequence,status);
    }
    return promise;
  }
  const facade={
    discover(name,options={}) {
      if(!options||typeof options!=='object')return rejected(ServiceStatus.invalid_request);
      const {major,minMinor,maxMinor,schema,source='automatic'}=options;
      if(!nameValid(name)||!integer(major,1,65535)||!integer(minMinor,0,65535)||
         !integer(maxMinor,minMinor,65535)||!['automatic','native','module'].includes(source)||
         (schema!==undefined&&(!owned(schema)||lengthOf.call(schema)!==32)))return rejected(ServiceStatus.invalid_request);
      try {
        const query={name,major,minMinor,maxMinor,schema:schema===undefined?undefined:copy(schema)};
        const values=[[1,6,encoder.encode(name)],[2,1,scalar(major,4)],
          [3,1,scalar(minMinor,4)],[4,1,scalar(maxMinor,4)]];
        if(schema!==undefined)values.push([5,7,query.schema]);
        return begin(0n,1,record(values),320,query,source);
      }catch{return rejected(ServiceStatus.limit_exceeded,'Could not allocate discovery request');}
    },
    receive(input) {
      if(closed||transportDepth||!owned(input)||lengthOf.call(input)<HEADER||lengthOf.call(input)>maxMessageBytes)return false;
      try {
        const bytes=copy(input),data=view(bytes),sequence=data.getBigUint64(24,true),entry=pending.get(sequence);
        const status=data.getUint32(48,true),payload=range(bytes,HEADER);
        if(!entry||data.getUint32(0,true)!==bytes.length||data.getUint16(4,true)!==1||data.getUint16(6,true)!==0||
           data.getUint32(8,true)!==4||data.getUint32(12,true)!==0||data.getBigUint64(16,true)!==generation||
           data.getBigUint64(32,true)!==entry.handle||data.getUint32(40,true)!==entry.operation||
           data.getUint32(44,true)!==payload.length||data.getUint32(52,true)!==0||data.getBigUint64(56,true)!==0n||
           !validStatus(status)||status===ServiceStatus.result_available||payload.length>entry.maxReplyBytes||
           (status!==ServiceStatus.ok&&payload.length!==0))return false;
        if(entry.completed) {
          if(!equal(entry.completion,bytes))return false;
          if(!entry.replay)return true;
        }
        let value;
        if(status===ServiceStatus.ok&&entry.query) {
          const selected=descriptor(payload,entry.query,maxMessageBytes-HEADER),serviceEpoch=epoch;
          value=Object.freeze({descriptor:selected,call:(operation,bytes)=>
            begin(selected.handle,operation,bytes,selected.maxReplyBytes,null,'automatic',serviceEpoch)});
        } else value=copy(payload);
        if(!entry.completed)entry.completion=bytes;
        entry.completed=true;
        settle(entry,sequence,status,value);
        return true;
      }catch{return false;}
    },
    acknowledge() {
      if(closed)return ServiceStatus.closed;
      if(transportDepth)return ServiceStatus.conflict;
      let through=acknowledged;
      for(const [sequence,entry] of pending) {if(!entry.completed)break;through=sequence;}
      if(through===acknowledged)return ServiceStatus.ok;
      const status=invoke('acknowledge',generation,through);
      if(closed)return ServiceStatus.closed;
      if(status===ServiceStatus.ok) {
        for(const [sequence,entry] of pending)if(sequence<=through) {
          pending.delete(sequence);retainedBytes-=entry.reserve;settle(entry,sequence,ServiceStatus.expired);
        }
        acknowledged=through;
      }
      return status;
    },
    resend(sequence) {
      if(closed)return ServiceStatus.closed;
      if(transportDepth)return ServiceStatus.conflict;
      const entry=u64(sequence)?pending.get(sequence):undefined;
      if(!entry)return u64(sequence)?ServiceStatus.expired:ServiceStatus.invalid_request;
      let submission;try{submission=copy(entry.bytes);}catch{return ServiceStatus.limit_exceeded;}
      const status=invoke('enqueue',submission,entry.source);
      if(closed)return ServiceStatus.closed;
      if(status===ServiceStatus.expired) {
        pending.delete(sequence);retainedBytes-=entry.reserve;settle(entry,sequence,status);
      }
      return status;
    },
    replay(sequence) {
      if(closed)return rejected(ServiceStatus.closed);
      if(transportDepth)return rejected(ServiceStatus.conflict);
      const entry=u64(sequence)?pending.get(sequence):undefined;
      if(!entry)return rejected(u64(sequence)?ServiceStatus.expired:ServiceStatus.invalid_request);
      if(entry.replay)return entry.replay.promise;
      let resolve,reject;
      const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});
      Object.defineProperty(promise,'sequence',{value:sequence,enumerable:true});
      const waiter={promise,resolve,reject};entry.replay=waiter;
      const status=facade.resend(sequence);
      if(status!==ServiceStatus.ok&&entry.replay===waiter) {
        entry.replay=null;reject(error(status,sequence));
      }
      return promise;
    },
    cancel(sequence) {
      if(closed)return ServiceStatus.closed;
      if(transportDepth)return ServiceStatus.conflict;
      const entry=u64(sequence)?pending.get(sequence):undefined;
      if(!entry)return u64(sequence)?ServiceStatus.expired:ServiceStatus.invalid_request;
      if(entry.completed)return ServiceStatus.conflict;
      const status=invoke('cancel',generation,sequence);
      if(closed)return ServiceStatus.closed;
      if(status===ServiceStatus.expired) {
        pending.delete(sequence);retainedBytes-=entry.reserve;settle(entry,sequence,status);
      }
      return status;
    },
    dispose() {
      if(closed)return;
      closed=true;++epoch;
      for(const [sequence,entry] of pending)settle(entry,sequence,ServiceStatus.closed);
      pending.clear();retainedBytes=0;
    }
  };
  return Object.freeze(facade);
}
