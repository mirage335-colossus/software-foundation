// Actual diagnostic decoder; no engine/Worker/browser/peer instance is created.
import fs from 'node:fs';
import {pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';
const [peerPath,codecPath]=process.argv.slice(2);
assert.equal(typeof peerPath,'string');assert.equal(typeof codecPath,'string');
const source=fs.readFileSync(peerPath,'utf8');
assert.equal(source.split("from './codecs.mjs'").length,2);
const linked=source.replace("from './codecs.mjs'",'from '+JSON.stringify(pathToFileURL(codecPath).href));
const {decodeDocumentReply}=await import('data:text/javascript;base64,'+Buffer.from(linked).toString('base64'));
function packet({caps=20,multiple=false,menu=true,label='',complete=true,truncated=false,readonly=false}={}){
 const a=[];const put=(n,w)=>{n=BigInt(n);for(let i=0;i<w;i++)a.push(Number((n>>BigInt(i*8))&255n));};
 const text=s=>{const b=Buffer.from(s);put(b.length,4);a.push(...b);};
 a.push(78,68,86,50,2,0,4,0);for(const n of [1,2,3,1,1,1,2,3,1,2,1])put(n,8);
 put(truncated?1:0,1);put(1,8);put(0,8);put(0,4);put(0,4);put(1,4);put(0,4);put(1,4);put(0,1);
 put(1,8);put(0,8);put(1,1);put(0,1);put(3,4);for(const s of ['select','','Visible menu','',''])text(s);
 put(1,8);put(multiple?5:4,1);put(4|(complete?32:0)|(readonly?2:0),1);put(caps,4);put(3,1);put(0,1);text(multiple?'select-multiple':'select-one');text('Visible menu');put((multiple?1:0)|(menu?2:0),1);put(3,4);
 for(const [node,flags,s]of [[2,1,'Alpha'],[3,4,label],[4,0,'Omega']]){put(node,8);put(flags,1);text(s);}
 return Uint8Array.from(a);
}
const expected={identity:{instance:1n,generation:2n,document:3n},sequence:1n,requestId:1n};
let checks=0;
for(const caps of [0,4,16,20]){const p=decodeDocumentReply(packet({caps}),expected).publication;assert.equal(p.forms.controls[0].complete,true);assert.equal(p.forms.controls[0].state.options[1].label,'');assert.equal(p.forms.controls[0].state.options[1].omitted,true);checks++;}
for(const bad of [{label:'leak'},{caps:8},{caps:8,multiple:true,menu:false},{caps:0,multiple:true},{menu:false},{complete:false},{truncated:true},{readonly:true}]){assert.throws(()=>decodeDocumentReply(packet(bad),expected));checks++;}
assert.equal(decodeDocumentReply(packet({caps:0,complete:false}),expected).publication.forms.controls[0].complete,false);checks++;
console.log(JSON.stringify({kind:'native-popup-peer-values-v1',checks,engine:false,worker:false,browser:false}));
