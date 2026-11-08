import assert from 'node:assert/strict';
import {readFileSync,readdirSync,existsSync} from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
export function checkSource(root){
 for(const name of ['content.js','app.js','teaching.js','manuscript-data.js']){const s=readFileSync(path.join(root,name),'utf8');new vm.Script(s);assert.doesNotMatch(s,/\bfetch\s*\(|XMLHttpRequest|localStorage|sessionStorage/);}
 for(const file of ['index.html','index-en.html']){const s=readFileSync(path.join(root,file),'utf8');assert.doesNotMatch(s,/src="(?:results-data|supplement-data)\.js"/);for(const m of s.matchAll(/(?:href|src)="([^"#]+)"/g))assert.ok(existsSync(path.resolve(root,m[1])));}
 const c=vm.createContext({});vm.runInContext(readFileSync(path.join(root,'teaching.js'),'utf8'),c);const T=c.DraftTeaching;
 assert.deepEqual(Array.from(T.models,m=>T.dimension(m)),[19,11,15,17,14]);assert.equal(T.weightedMedian(T.examples.report).threshold,0.8);assert.equal(T.weightedMedian(T.examples.report).highFraction,0.6);assert.equal(T.weightedMedian(T.examples.ties).highFraction,5/6);for(const rows of [[],[{score:1,weight:-1}],[{score:1,weight:0}]])assert.throws(()=>T.weightedMedian(rows));
 function lf(dir){for(const e of readdirSync(dir,{withFileTypes:true})){const f=path.join(dir,e.name);if(e.isDirectory()){if(e.name!=='__pycache__')lf(f);}else if(/\.(js|mjs|py|html|css|md)$/.test(f))assert.ok(!readFileSync(f).includes(13),f);}}lf(root);
 console.log('PASS: script syntax; offline resources; no historical startup dependency; weighted-median examples; LF.');
}
