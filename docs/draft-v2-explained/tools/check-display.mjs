/** Current report/source consistency only: no event or original aggregate access. */
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {createHash} from 'node:crypto';
import path from 'node:path';
import vm from 'node:vm';
export function checkDisplay(root){
 const read=n=>readFileSync(path.resolve(root,n),'utf8');
 const load=lang=>{const c=vm.createContext({document:{documentElement:{lang}}});for(const n of ['teaching.js','manuscript-data.js','content.js'])vm.runInContext(read(n),c);return c;};
 const zh=load('zh-CN'),en=load('en'),D=JSON.parse(JSON.stringify(zh.DraftManuscript));
 assert.equal(D.report_artifact_id,'a7e610a163e5d155705014201b7ee330323e3bf69309e0e89b2496edba5d4317');
 assert.equal(D.local_aggregate_verification,false);assert.equal(D.rows.length,15);assert.equal(D.deltas.length,12);
 const report=read('../../paper/draft-v2/project-report-cn.tex'),evidence=read('../../paper/draft-v2/BASIC-20261108-EVIDENCE.md');
 for(const [f,hash]of Object.entries(D.source_files))assert.equal(createHash('sha256').update(readFileSync(path.resolve(root,'../..',f))).digest('hex'),hash,f);
 for(const id of [D.report_artifact_id,...Object.values(D.binding)])assert.ok(evidence.includes(id));
 for(const row of D.rows)assert.ok(report.includes([row.subset,row.seed,row.S,row.B,row.RS,row.RB,row.Q].join(' & ')));
 for(const row of D.deltas){const key={RS:'R_S',RB:'R_B',Q:'Q'}[row.metric];assert.ok(report.includes(`${row.group} & $\\Delta ${key}$ & `+[...row.values,row.median,row.range].map(v=>'$'+v+'$').join(' & ')));}
 for(const r of D.yield_rows)for(const cell of r.slice(2)){const [v,e]=cell.replace('%','').split(' ± ');assert.ok(report.includes(v+'\\pm'+e));}
 for(const values of Object.values(D.mass_fractions_percent))for(const value of values)assert.ok(report.includes(value.toFixed(1)));
 for(const name of ['mass-yields','mass-shapes','deletion-differences'])assert.ok(evidence.includes(D.source_files[`paper/draft-v2/figures/basic-20261108/${name}.pdf`]));
 assert.deepEqual(Array.from(zh.DraftContent.slides,s=>s.id),Array.from(en.DraftContent.slides,s=>s.id));
 for(const c of [zh,en]){const slides=c.DraftContent.slides;assert.equal(slides.length,40);assert.equal(new Set(slides.map(s=>s.id)).size,40);assert.equal(slides.filter(s=>s.supervisorRelated).length,4);
 for(const s of slides){const html=s.body+s.notes;assert.ok(s.title&&s.lead&&s.source&&s.notes.includes('<p>'));assert.doesNotMatch(html,/\bNaN\b|\bundefined\b/);if(c.DraftContent.en)assert.doesNotMatch(s.title+s.lead+html,/[\u4e00-\u9fff]/);
 assert.equal(s.sourceFile,'project-report-cn.tex');assert.doesNotMatch(s.body,/W₆₈|W68|60\.4%|67\.2%|24,000|1\.464392/);
 for(const m of html.matchAll(/(?:href|src|data)="([^"]+)"/g)){if(m[1].startsWith('#'))assert.notEqual(c.DraftTeaching.pageFromHash(slides,m[1],0),0);else assert.ok(existsSync(path.resolve(root,m[1].split('#')[0])),m[1]);}}
 for(const m of ['ABCD','BCD','ACD','ABD','ABC'])assert.equal(D.rows.filter(r=>r.subset===m).length,3);
 const reversed=Array.from(slides).reverse();for(const id of ['all-results','contrasts','spectrum-yields','provenance'])assert.equal(c.DraftTeaching.pageFromHash(reversed,'#'+id),reversed.findIndex(s=>s.id===id)+1);
 assert.equal(c.DraftTeaching.pageFromHash(slides,'#widths'),slides.findIndex(s=>s.id==='all-results')+1);
 }
 assert.deepEqual(D.qualification,{status:'exploratory_posthoc',independent:false,selection_aware_coverage:'unvalidated',primary_claim_eligible:false});
 console.log('PASS: both 40-slide basic-report editions; 15 metric rows; 12 contrast rows; current report identities and PDF hashes; local links; translations; historical-result isolation.');
}
