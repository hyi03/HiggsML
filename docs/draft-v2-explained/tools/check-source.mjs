import assert from 'node:assert/strict';
import {readFileSync,readdirSync,existsSync} from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
export function checkSource(root){
 for(const name of ['content.js','app.js','teaching.js','manuscript-data.js']){const s=readFileSync(path.join(root,name),'utf8');new vm.Script(s);assert.doesNotMatch(s,/\bfetch\s*\(|XMLHttpRequest|localStorage|sessionStorage/);}
 for(const file of ['index.html','index-en.html']){const s=readFileSync(path.join(root,file),'utf8');assert.doesNotMatch(s,/src="(?:results-data|supplement-data)\.js"/);for(const m of s.matchAll(/(?:href|src)="([^"#]+)"/g))assert.ok(existsSync(path.resolve(root,m[1])));}
 const c=vm.createContext({});vm.runInContext(readFileSync(path.join(root,'teaching.js'),'utf8'),c);const T=c.DraftTeaching;
 assert.deepEqual(Array.from(T.models,m=>T.dimension(m)),[19,11,15,17,14]);assert.equal(T.weightedMedian(T.examples.report).threshold,0.8);assert.equal(T.weightedMedian(T.examples.report).highFraction,0.6);assert.equal(T.weightedMedian(T.examples.ties).highFraction,5/6);for(const rows of [[],[{score:1,weight:-1}],[{score:1,weight:0}]])assert.throws(()=>T.weightedMedian(rows));
 const near=(a,b)=>assert.ok(Math.abs(a-b)<1e-13,`${a} != ${b}`);
 const r=T.tinyForward(T.toyDefaults.pt,T.toyDefaults.phi);
 assert.deepEqual(Array.from(r.x),[0,0]);assert.deepEqual(Array.from(r.a),[0.1,-0.2]);
 near(r.h[0],0.052497918747894);near(r.h[1],-0.09003320053750444);
 near(r.z,0.1602713672493577);near(r.score,0.539982293295586);
 const shifted=T.tinyForward(60,1.6);assert.deepEqual(Array.from(shifted.x),[1,0]);near(shifted.a[0],0.7);near(shifted.a[1],-0.5);
 for(const pt of [0,40,60,160])for(const phi of [0,1.6,Math.PI]){
  const v=T.tinyForward(pt,phi);for(const n of [...v.x,...v.a,...v.h,v.z,v.score])assert.ok(Number.isFinite(n));assert.ok(v.score>0&&v.score<1);
 }
 for(const values of [[NaN,1],[40,Infinity],[-1,0],[161,0],[0,-1],[0,Math.PI+0.01],['40',1]])assert.throws(()=>T.tinyForward(...values));
 function lf(dir){for(const e of readdirSync(dir,{withFileTypes:true})){const f=path.join(dir,e.name);if(e.isDirectory()){if(e.name!=='__pycache__')lf(f);}else if(/\.(js|mjs|py|html|css|md)$/.test(f))assert.ok(!readFileSync(f).includes(13),f);}}lf(root);
 console.log('PASS: script syntax; offline resources; no historical startup dependency; weighted-median examples; artificial forward-pass default, intermediate precision, boundaries and invalid inputs; LF.');
}
