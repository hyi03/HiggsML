/** Current-manuscript/site consistency checks, without event or model access. */
import assert from 'node:assert/strict';
import {readFileSync,existsSync,readdirSync} from 'node:fs';
import {createHash} from 'node:crypto';
import path from 'node:path';
import vm from 'node:vm';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const read=name=>readFileSync(path.join(root,name),'utf8');
function load(lang){
 const ctx=vm.createContext({document:{documentElement:{lang}}});
 for(const name of ['teaching.js','results-data.js','content.js'])vm.runInContext(read(name),ctx,{filename:name});
 return ctx;
}
const zh=load('zh-CN'),en=load('en'),D=JSON.parse(JSON.stringify(zh.DraftResults));
assert.equal(D.report_artifact_id,'9aab6d274a3e2d00d892c2d8fbf89b1e46f5b7a95d0bf0c085af90672ea36898');
assert.equal(D.schema_version,'draft-v2-website-results-v1');
assert.equal(D.source_kind,'controlled_mc');
assert.equal(D.summary.scientific_status,'complete');
assert.equal(D.summary.qualification.independent,false);
assert.equal(D.summary.qualification.primary_claim_eligible,false);
assert.equal(D.summary.qualification.selection_aware_coverage,'unvalidated');
assert.deepEqual(D.summary.seeds,[42,43,44]);
assert.deepEqual(D.protocol.roles,{train:0.6,validation:0.2,evaluation:0.2});
assert.equal(Object.keys(D.intervals).length,16);
for(const interval of Object.values(D.intervals))assert.equal(interval.status,'valid');
const near=(a,b)=>assert.ok(Math.abs(a-b)<1e-12,`${a} != ${b}`);
const median=values=>[...values].sort((a,b)=>a-b)[1];
for(const row of D.summary.rows){
 near(row.median,median(row.widths));
 row.widths.forEach((w,i)=>near(w,D.intervals[`${row.subset}:${42+i}`].width));
}
const full=D.summary.rows[0];
for(const row of D.summary.contrasts){
 const reduced=D.summary.rows.find(r=>r.subset===row.reduced);
 row.differences.forEach((d,i)=>near(d,reduced.widths[i]-full.widths[i]));
 near(row.median_difference,median(row.differences));
}
const B=D.summary.contrasts.find(r=>r.removed_group==='B');
assert.ok(B.median_difference<0);
assert.ok(D.summary.rows.find(r=>r.subset==='ACD').median-full.median>0);
near(D.summary.inclusive_width,D.intervals.inclusive.width);
for(const name of ['mass-yields.png','mass-shapes.png','widths.csv','contrasts.csv','inclusive-reference.csv','mass-bins.csv','yield-summary.csv']){
 const bytes=readFileSync(path.join(root,'assets','draft001-'+name));
 assert.equal(bytes.length,D.consumed_files[name].size_bytes);
 assert.equal(createHash('sha256').update(bytes).digest('hex'),D.consumed_files[name].sha256);
}
for(const name of ['ABCD','BCD'])for(const [process,v] of Object.entries(D.models[name].processes)){
 near(v.retention,v.totals[1]/v.totals[0]);
 assert.equal(v.group_count.slice(0,7).reduce((a,b)=>a+b,0),process==='signal'?9049:698);
 assert.equal(v.covariance.length,14);assert.equal(v.shape_covariance.length,14);
 near(v.fractions.slice(0,7).reduce((a,b)=>a+b,0),1);
 near(v.fractions.slice(7).reduce((a,b)=>a+b,0),1);
}
assert.ok(D.models.ABCD.processes.background.yields[7]<0);
const tex=readFileSync(path.resolve(root,'../../paper/draft-v2/draft001-tables.tex'),'utf8');
for(const row of D.summary.rows)for(const n of [...row.widths,row.median])assert.ok(tex.includes(n.toFixed(6)));
for(const row of D.summary.contrasts)for(const n of [...row.differences,row.median_difference])assert.ok(tex.includes((n>=0?'+':'')+n.toFixed(6)));
assert.equal(zh.DraftContent.slides.length,32);assert.equal(en.DraftContent.slides.length,32);
assert.deepEqual(Array.from(zh.DraftContent.slides,s=>s.id),Array.from(en.DraftContent.slides,s=>s.id));
assert.equal(new Set(zh.DraftContent.slides.map(s=>s.id)).size,32);
for(const ctx of [zh,en]){
 for(const s of ctx.DraftContent.slides){
  for(const key of ['id','chapter','title','lead','body','notes','source'])assert.ok(s[key],`${s.id}: ${key}`);
  assert.ok(s.notes.includes('<p>'),s.id+': substantive notes');
  const html=s.body+s.notes;
  assert.doesNotMatch(html,/\bNaN\b|\bundefined\b|results? pending|unexecuted proposal|新版.*未执行|结果待生成|待运行/);
  if(ctx.DraftContent.en)assert.doesNotMatch(s.title+s.lead+html,/[\u4e00-\u9fff]/,s.id+': untranslated English');
  for(const m of html.matchAll(/(?:href|src)="([^"]+)"/g))if(!/^https?:|^#/.test(m[1]))assert.ok(existsSync(path.resolve(root,m[1].split('#')[0])),m[1]);
  assert.ok(existsSync(path.resolve(root,'../../paper/draft-v2',s.sourceFile||'main.tex')));
 }
 const widths=ctx.DraftContent.slides.find(s=>s.id==='widths').body;
 for(const row of D.summary.rows)for(const n of row.widths)assert.ok(widths.includes(n.toFixed(6)));
 const contrasts=ctx.DraftContent.slides.find(s=>s.id==='contrasts').body;
 for(const row of D.summary.contrasts)for(const n of row.differences)assert.ok(contrasts.includes(Math.abs(n).toFixed(6)));
 for(const id of ['model-output','median-output','contrast-output','width-output'])assert.equal(ctx.DraftContent.slides.filter(s=>s.body.includes(`id="${id}"`)).length,1);
}
const T=zh.DraftTeaching;
assert.deepEqual(Array.from(T.models,m=>T.dimension(m)),[19,11,15,17,14]);
assert.equal(T.weightedMedian(T.examples.ties).highFraction,5/6);
assert.equal(T.weightedMedian(T.examples.balanced).threshold,0.3);
assert.equal(T.weightedMedian(T.examples.unequal).highFraction,1);
assert.equal(T.weightedMedian([...T.examples.ties].reverse()).threshold,0.35);
assert.equal(T.weightedMedian([{score:0,weight:0},{score:1,weight:2}]).threshold,1);
for(const rows of [[],[{score:1,weight:0}],[{score:1,weight:-1}],[{score:NaN,weight:1}]])assert.throws(()=>T.weightedMedian(rows));
for(const file of ['index.html','index-en.html']){
 const html=read(file);assert.match(html,/src="results-data.js"/);
 assert.doesNotMatch(html,/historical-data.js|spectra-data.js|未执行|unexecuted/);
 for(const m of html.matchAll(/(?:href|src)="([^"]+)"/g))if(!/^https?:|^#/.test(m[1]))assert.ok(existsSync(path.resolve(root,m[1])));
}
for(const file of ['content.js','teaching.js','app.js']){
 const source=read(file);new vm.Script(source,{filename:file});
 assert.doesNotMatch(source,/\bfetch\s*\(|XMLHttpRequest|localStorage|sessionStorage/);
 assert.doesNotMatch(source,/HistoricalIllustration|HistoricalSpectra|Unexecuted proposal|Results pending/);
}
function lf(dir){for(const ent of readdirSync(dir,{withFileTypes:true})){const f=path.join(dir,ent.name);if(ent.isDirectory()){if(ent.name!=='__pycache__')lf(f);}else if(/\.(js|mjs|py|html|css|md)$/.test(f))assert.ok(!readFileSync(f).includes(13),f);}}
lf(root);
console.log('PASS: 32 current aligned slides; complete translations; manuscript/table arithmetic; bound assets; grouped spectrum statistics; shared reference; paired-median sign example; teaching boundaries; local links; offline runtime; LF.');
