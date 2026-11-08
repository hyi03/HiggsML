/* Shared offline navigation and educational widgets for both language editions. */
(() => {
  'use strict';
  const {slides,t,en} = DraftContent;
  const $ = selector => document.querySelector(selector);
  const count = slides.length;
  const sourceLink = slide => `${slide.teaching?t('教学扩展（基于报告）','Teaching expansion (based on report)'):t('当前基础报告','Current basic report')}: <a href="../../paper/draft-v2/${slide.sourceFile || 'project-report-cn.tex'}" target="_blank" rel="noopener">${slide.source}</a>`;
  $('#deck').innerHTML = slides.map((s,i) => `<section class="slide" id="slide-${i+1}" aria-labelledby="title-${i+1}"${i?' hidden':''}><header class="slide-header"><p class="section-label">${s.chapter}${s.supervisorRelated?` <span class="supervisor-badge">${t('导师要求 · 直接回应','Supervisor request · Direct response')}</span>`:''}</p><${i?'h2':'h1'} id="title-${i+1}">${s.title}</${i?'h2':'h1'}><p class="lead">${s.lead}</p></header><div class="slide-content"><div class="slide-body" tabindex="0" aria-label="${t('本页图表与要点','Figures and key points')}">${s.body}</div><div class="slide-explanation" role="region" tabindex="0" aria-label="${t('本页讲解','Explanation for this slide')}">${s.notes}</div></div><footer class="slide-footer"><span>${sourceLink(s)}</span><span>${s.teaching?t('人工教学解释 · 非研究结果','Teaching explanation · Not research results'):t('draft001 · 论文显示精度 · 探索性','draft001 · Manuscript display precision · Exploratory')} · ${String(i+1).padStart(2,'0')} / ${count}</span></footer></section>`).join('');
  $('#page').max = count;
  $('#page-count').textContent = count;
  $('#toc-title').textContent = t(`${count} 页学习路线`,`${count}-slide learning route`);
  $('#toc-list').innerHTML = slides.map((s,i) => `<li><a href="#${s.id}"><span>${String(i+1).padStart(2,'0')}</span>${s.title}</a></li>`).join('');

  function showModel(model) {
    const omitted = [...'ABCD'].find(g => !model.includes(g));
    document.querySelectorAll('.model-option').forEach(b => b.setAttribute('aria-pressed',String(b.dataset.model===model)));
    $('#model-output').innerHTML = `<span class="dimension-number">${DraftTeaching.dimension(model)}</span> ${t('个输入','inputs')} · <strong>${model}</strong> · ${omitted?t(`移除 ${omitted}`,`Omit ${omitted}`):t('完整表示','Full representation')}<div class="model-features">${[...'ABCD'].map(g=>`<span class="${model.includes(g)?'':'omitted'}">${g}: ${DraftTeaching.dimensions[g]}</span>`).join('')}</div>`;
  }
  document.querySelectorAll('.model-option').forEach(b => b.addEventListener('click',() => showModel(b.dataset.model)));
  showModel('ABCD');

  function showMedian() {
    const rows = DraftTeaching.examples[$('#median-example').value];
    const r = DraftTeaching.weightedMedian(rows);
    $('#median-output').innerHTML = `<div class="score-track">${rows.map(row=>`<div class="score-token ${row.score>=r.threshold?'high':''}"><b>${row.score}</b>${t('权重','weight')} ${row.weight} · ${row.score>=r.threshold?t('高侧','high'):t('低侧','low')}</div>`).join('')}</div><div class="result-line">${t('阈值','Threshold')} = <strong>${r.threshold}</strong> · ${t('高侧绝对权重','High-side absolute weight')} = ${r.highWeight}/${r.total} (${(100*r.highFraction).toFixed(1)}%)</div><p class="small">${t('教学例子；绿色为评分 ≥ 阈值，所有并列评分保留在同侧。','Teaching example; green means score ≥ threshold. All tied scores stay together.')}${r.highWeight===r.total?t(' 该例低侧为空；在研究中须保留不支持状态。',' This example leaves the low category empty; the study must retain an unsupported status.'):''}</p>`;
  }
  $('#median-example').addEventListener('change',showMedian);
  showMedian();

  function showForward() {
    const pt=Number($('#toy-pt').value),phi=Number($('#toy-phi').value);
    const r=DraftTeaching.tinyForward(pt,phi), fmt=value=>value.toFixed(4);
    $('#toy-pt-value').value=fmt(pt);
    $('#toy-phi-value').value=fmt(phi);
    const stage=(label,body)=>`<div class="nn-stage"><h3>${label}</h3>${body}</div>`;
    const node=(label,value)=>`<div class="nn-node"><span>${label}</span><strong>${fmt(value)}</strong></div>`;
    const arrow='<span class="nn-arrow" aria-hidden="true">→</span>';
    $('#toy-output').innerHTML=`<div class="nn-forward" role="group" aria-label="${t('人工前向计算的四个步骤','Four stages of the artificial forward calculation')}">${[
      stage(t('1 · 标准化','1 · Scale'),node('x₁=(pT−40)/20',r.x[0])+node('x₂=(|Δφ|−1.6)/0.8',r.x[1])),
      stage(t('2 · 加权求和','2 · Weighted sums'),node('a₁=0.6x₁−0.4x₂+0.1',r.a[0])+node('a₂=−0.3x₁+0.8x₂−0.2',r.a[1])),
      stage(t('3 · 非线性','3 · Nonlinearity'),node('h₁=SiLU(a₁)',r.h[0])+node('h₂=SiLU(a₂)',r.h[1])),
      stage(t('4 · 输出','4 · Output'),node('z=0.9h₁−0.7h₂+0.05',r.z)+node('s=sigmoid(z)',r.score))
    ].join(arrow)}</div><p class="small">${t('每个隐藏节点接收 x₁ 和 x₂。固定人工参数，仅改变输入；没有学习、真实模型评分或阈值判断。','Each hidden node receives x₁ and x₂. Artificial parameters stay fixed while inputs change; no learning, actual model scoring or threshold decision occurs.')}</p>`;
  }
  for(const id of ['toy-pt','toy-phi']) $('#'+id).addEventListener('input',showForward);
  $('#toy-reset').addEventListener('click',()=>{
    $('#toy-pt').value=DraftTeaching.toyDefaults.pt;
    $('#toy-phi').value=DraftTeaching.toyDefaults.phi;
    showForward();
  });
  showForward();

  const number = (v,d=3) => Number(v).toFixed(d);
  const sign = (v,d=3) => (v>=0?'+':'−')+Math.abs(v).toFixed(d);
  const median = a => [...a].sort((x,y)=>x-y)[1];
  function showContrast() {
    const group=$('#removed-group').value, metric=$('#contrast-metric').value;
    const row=DraftManuscript.deltas.find(r=>r.group===group&&r.metric===metric);
    const reduced=DraftTeaching.reduced(group), d=metric==='Q'?3:2;
    const values=model=>DraftManuscript.rows.filter(r=>r.subset===model).map(r=>Number(r[metric]));
    const alternate=median(values(reduced))-median(values('ABCD'));
    $('#contrast-output').innerHTML=`<p>Δ${metric}: ${reduced} − ABCD ${metric==='Q'?'':'(pp)'}</p><div class="contrast-seeds">${row.values.map((v,i)=>`<div><span>Seed ${42+i}</span><strong>${v}</strong></div>`).join('')}</div><div class="calculation selected"><span>${t('报告配对差值中位数','Recorded median paired contrast')}</span><strong>${row.median}</strong></div><div class="calculation"><span>${t('显示精度下的两组中位数之差','Difference of medians at display precision')}</span><strong>${sign(alternate,d)}</strong></div><p>${t('记录范围','Recorded range')}: ${row.range}. ${t('不是置信区间。','Not a confidence interval.')}</p>`;
  }
  for(const id of ['removed-group','contrast-metric']) $('#'+id).addEventListener('change',showContrast);
  showContrast();
  function showWidths() {
    const seed=Number($('#width-seed').value),metric=$('#basic-metric').value;
    const max=metric==='Q'?3:100, d=metric==='Q'?3:2;
    const rows=DraftManuscript.rows.filter(r=>r.seed===seed);
    $('#width-output').innerHTML=`<p>Seed ${seed} · ${metric}${metric==='Q'?'':' (%)'}</p><div class="width-axis"><span>0</span><span>${max}</span></div><div class="width-bars">${rows.map(r=>`<div class="width-row"><span>${r.subset}</span><div class="bar-track"><div style="width:${100*Number(r[metric])/max}%"></div></div><strong>${number(r[metric],d)}</strong></div>`).join('')}</div><p>${t('直接显示报告值；没有添加误差条或显著性。','Displays report values without added error bars or significance.')}</p>`;
  }
  for(const id of ['width-seed','basic-metric']) $('#'+id).addEventListener('change',showWidths);
  showWidths();

  let current = 1;
  const clamp = value => Math.max(1, Math.min(count, Number.isFinite(value)?Math.round(value):1));
  const fromHash = () => DraftTeaching.pageFromHash(slides, location.hash, current);
  function render() {
    current = fromHash();
    document.querySelectorAll('.slide').forEach((s,i) => {s.hidden = i+1!==current;});
    $('#page').value = current;
    $('#prev').disabled = current===1;
    $('#next').disabled = current===count;
    $('#chapter-status').textContent = slides[current-1].chapter;
    $('#progress-fill').style.width = `${100*current/count}%`;
    $('#language-link').href = `${en?'index.html':'index-en.html'}#slide-${current}`;
    $('#announcement').textContent = t(`第 ${current} 页，共 ${count} 页。${slides[current-1].title}`,`Slide ${current} of ${count}. ${slides[current-1].title}`);
    document.title = `${current}/${count} ${slides[current-1].title} · HiggsML Draft v2`;
    document.querySelectorAll('#toc-list a').forEach((a,i) => i+1===current?a.setAttribute('aria-current','page'):a.removeAttribute('aria-current'));
  }
  function go(value) {
    const next = clamp(value);
    if (next===current) render();
    else location.hash = `slide-${next}`;
    window.scrollTo({top:0,behavior:'instant'});
  }
  $('#prev').addEventListener('click',()=>go(current-1));
  $('#next').addEventListener('click',()=>go(current+1));
  $('#page').addEventListener('change',e=>go(Number(e.target.value)));
  $('#page').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();go(Number(e.target.value));}});
  $('#jump').addEventListener('click',()=>go(Number($('#page').value)));
  $('#toc-button').addEventListener('click',()=>$('#toc').showModal());
  $('#toc-close').addEventListener('click',()=>$('#toc').close());
  $('#toc').addEventListener('click',e=>{if(e.target.closest('a')) $('#toc').close();});
  $('#full-button').addEventListener('click',async()=>{
    try {
      if(document.fullscreenElement) await document.exitFullscreen();
      else await document.documentElement.requestFullscreen();
    } catch {
      $('#announcement').textContent=t('此环境未能进入全屏，请使用浏览器全屏菜单。','Fullscreen is unavailable here; use the browser fullscreen menu.');
    }
  });
  document.addEventListener('fullscreenchange',()=>{$('#full-button').textContent=document.fullscreenElement?t('退出全屏','Exit fullscreen'):t('全屏','Fullscreen');});
  $('#print-button').addEventListener('click',()=>window.print());
  document.addEventListener('keydown',e=>{
    if($('#toc').open || e.altKey || e.ctrlKey || e.metaKey || e.target.closest('input,select,textarea,button,a,summary,.table-wrap[tabindex],.slide-body,.slide-explanation,[contenteditable="true"]')) return;
    const keys={ArrowRight:current+1,PageDown:current+1,ArrowLeft:current-1,PageUp:current-1,Home:1,End:count};
    if(e.key in keys){e.preventDefault();go(keys[e.key]);}
    else if(e.key===' '){e.preventDefault();go(current+(e.shiftKey?-1:1));}
  });
  window.addEventListener('hashchange',render);
  render();
})();
