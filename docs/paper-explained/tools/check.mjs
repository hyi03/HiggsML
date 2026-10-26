// Compare the teaching arithmetic with independently stored selected aggregates.
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const context=vm.createContext({});
for(const name of ['data.js','math.js','visuals.js','content.js'])vm.runInContext(fs.readFileSync(path.join(root,name),'utf8'),context,{filename:name});
const {H4L:H,H4L_DATA:D,SLIDES}=context;
const close=(a,b,msg)=>assert.ok(Math.abs(a-b)<=1e-12+1e-12*Math.abs(b),`${msg}: ${a} vs ${b}`);
assert.equal(SLIDES.length,33);
assert.equal(D.records.length,80);
assert.equal(new Set(D.records.map(r=>`${r.seed}:${r.subset}`)).size,80);
assert.ok(D.records.every(r=>r.status==='valid'));
assert.equal(D.subsets.length,16);
assert.equal(new Set(SLIDES.map(s=>s.title)).size,33);
assert.ok(SLIDES.every(s=>s.notes.length>120&&s.source&&s.body));
assert.equal(D.source.report_artifact_id,'baede583dc2ef36330af1184d266833f3e64a3179fc8d5ce8bff1b6867307cb5');
assert.equal(D.source.snapshot_sha256,'f9cf1470480f8c8fab971077c7947361ffb5cd47f44502dafedd977687a3794f');
assert.deepEqual(Array.from(H.rank()).map(r=>r.subset),['BC','AC','ABC','BCD','ABCD','B','BD','ABD','AB','ACD','C','CD','A','AD','D']);
assert.equal(H.rank('median','auc')[0].subset,'AC');
for(const k of D.seeds){
  close(H.width('',k),H.width('',42),'Constant baseline');
  let total=0;
  for(const g of 'ABCD'){
    const phi=H.shapley(g,k);total+=phi;
    close(phi,D.attribution.find(r=>r.group===g).per_seed[D.seeds.indexOf(k)],`Stored Shapley ${g}/${k}`);
    const byOrder=H.orders.map(order=>{const s=order.slice(0,order.indexOf(g)).join('');return H.gain(s,g,k);}).reduce((a,b)=>a+b,0)/24;
    close(phi,byOrder,'Permutation vs weighted Shapley');
  }
  close(total,H.width('',k)-H.width('ABCD',k),'Efficiency identity');
}
for(const r of D.interactions){const pair=r.pair.startsWith('[')?JSON.parse(r.pair).join(''):r.pair;
  D.seeds.forEach((k,i)=>close(H.interaction(pair,r.conditioning_subset,k),r.per_seed[i],`Interaction ${pair}/${r.conditioning_subset}/${k}`));
  close(H.median(D.seeds.map(k=>H.interaction(pair,r.conditioning_subset,k))),r.median,'Interaction median');
}
for(const r of D.pairwise){D.seeds.forEach((k,i)=>{
  close(H.reduction(r.left,r.right,k),r.relative_improvement_left_vs_right.per_seed[i],'Paired ratio');
  close(H.width(r.left,k)-H.width(r.right,k),r.delta_width68_left_minus_right.per_seed[i],'Paired difference');
});close(H.median(D.seeds.map(k=>H.reduction(r.left,r.right,k))),r.relative_improvement_left_vs_right.median,'Paired median');}
for(const split of [true,false]){close(H.toyQ(1,split),0,'T0 minimum');for(const upper of [true,false])close(H.toyQ(H.crossing(split,upper),split),.9889464815,'T0 interval endpoint');}
assert.ok(H.crossing(true,true)-H.crossing(true,false)<H.crossing(false,true)-H.crossing(false,false));
for(const g of 'ABCD'){const range=H.mc('contributions',{group:g});assert.ok(range[0]<range[1]);}
const englishContext=vm.createContext({});
for(const name of ['data.js','math.js','en/visuals.js','en/content.js'])vm.runInContext(fs.readFileSync(path.join(root,name),'utf8'),englishContext,{filename:name});
const englishSlides=englishContext.SLIDES;
assert.equal(englishSlides.length,SLIDES.length,'Language editions have matching slide counts');
assert.equal(new Set(englishSlides.map(s=>s.title)).size,33);
for(const [i,s] of englishSlides.entries()){
  assert.ok(s.notes.length>120&&s.source&&s.body,`English slide ${i+1} is complete`);
  assert.ok(!/[\u4e00-\u9fff]/u.test(s.chapter+s.title+s.lead+s.body+s.notes+s.source),`Untranslated English slide ${i+1}`);
  assert.equal(s.figure,SLIDES[i].figure,`Figure binding on slide ${i+1}`);
  const widgets=s=>Array.from(s.body.matchAll(/data-widget="([^"]+)"/g),m=>m[1]);
  assert.deepEqual(widgets(s),widgets(SLIDES[i]),`Interactive page correspondence ${i+1}`);
}
for(const name of ['index.html','index-en.html']){
  const index=fs.readFileSync(path.join(root,name),'utf8');
  for(const match of index.matchAll(/(?:src|href)="([^"]+)"/g)){if(match[1].startsWith('#'))continue;assert.ok(fs.existsSync(path.join(root,match[1])),match[1]);}
  assert.ok(index.includes('src="data.js"')&&index.includes('src="math.js"'),'Both editions share data and arithmetic');
}
for(const slide of [...SLIDES,...englishSlides]){
  if(slide.figure)assert.ok(fs.existsSync(path.join(root,'../../paper/latex/figures',`${slide.figure}.pdf`)),slide.figure);
  for(const match of `${slide.body}${slide.notes}`.matchAll(/href="([^"]+)"/g)){
    if(match[1].startsWith('#'))continue;
    assert.ok(!/^https?:/.test(match[1]),`Unexpected external dependency: ${match[1]}`);
    assert.ok(fs.existsSync(path.join(root,match[1])),match[1]);
  }
}
for(const name of fs.readdirSync(root,{recursive:true}).filter(n=>/\.(js|mjs|py|css|html|md)$/.test(n))){assert.ok(!fs.readFileSync(path.join(root,name)).includes(13),`CRLF in ${name}`);}
console.log(JSON.stringify({slides:SLIDES.length,englishSlides:englishSlides.length,nominal:80,shapley:20,interactions:120,pairwise:525,toyEndpoints:4,status:'passed'}));
