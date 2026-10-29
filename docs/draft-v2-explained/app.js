/* Shared offline navigation and educational widgets for both language editions. */
(() => {
  'use strict';
  const {slides,t,en} = DraftContent;
  const $ = selector => document.querySelector(selector);
  const count = slides.length;
  const sourceLink = slide => `<a href="../../paper/draft-v2/${slide.sourceFile || 'main.tex'}" target="_blank" rel="noopener">${slide.source}</a>`;
  $('#deck').innerHTML = slides.map((s,i) => `<section class="slide" id="slide-${i+1}" aria-labelledby="title-${i+1}"${i?' hidden':''}><header class="slide-header"><p class="section-label">${s.chapter}${s.supervisorRelated?` <span class="supervisor-badge">${t('导师要求 · 直接回应','Supervisor request · Direct response')}</span>`:''}</p><${i?'h2':'h1'} id="title-${i+1}">${s.title}</${i?'h2':'h1'}><p class="lead">${s.lead}</p></header><div class="slide-content"><div class="slide-body" tabindex="0" aria-label="${t('本页图表与要点','Figures and key points')}">${s.body}</div><div class="slide-explanation" role="region" tabindex="0" aria-label="${t('本页讲解','Explanation for this slide')}">${s.notes}</div></div><footer class="slide-footer"><span>${sourceLink(s)}</span><span>${t('draft001 · 探索性 MC 结果','draft001 · Exploratory MC results')} · ${String(i+1).padStart(2,'0')} / ${count}</span></footer></section>`).join('');
  $('#page').max = count;
  $('#page-count').textContent = count;
  $('#toc-title').textContent = t(`${count} 页学习路线`,`${count}-slide learning route`);
  $('#toc-list').innerHTML = slides.map((s,i) => `<li><a href="#slide-${i+1}"><span>${String(i+1).padStart(2,'0')}</span>${s.title}</a></li>`).join('');

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

  const number = value => Number(value).toFixed(6);
  const sign = value => (value >= 0 ? '+' : '−') + Math.abs(value).toFixed(6);
  function showContrast() {
    const group = $('#removed-group').value;
    const row = DraftResults.summary.contrasts.find(r => r.removed_group === group);
    const full = DraftResults.summary.rows.find(r => r.subset === 'ABCD');
    const reduced = DraftResults.summary.rows.find(r => r.subset === row.reduced);
    const deltaMedian = reduced.median - full.median;
    $('#contrast-output').innerHTML = `<div class="comparison-formula">ΔW<sub>${group}</sub>(k) = W₆₈(${row.reduced}, k) − W₆₈(ABCD, k)</div><div class="contrast-seeds">${row.differences.map((v,i)=>`<div><span>Seed ${42+i}</span><strong>${sign(v)}</strong></div>`).join('')}</div><div class="calculation selected"><span>${t('论文规则：配对差值中位数','Manuscript rule: median of paired contrasts')}</span><strong>${sign(row.median_difference)}</strong></div><div class="calculation"><span>${t('另一统计量：宽度中位数之差','Different statistic: difference of width medians')}</span><strong>${sign(deltaMedian)}</strong></div><p class="small">${t('先相减再取中位数；完整精度计算后显示六位小数。','Subtract before taking the median; compute at full precision, then display six decimals.')}</p>`;
  }
  $('#removed-group').addEventListener('change',showContrast);
  showContrast();
  function showWidths() {
    const view = $('#width-seed').value;
    const index = DraftResults.summary.seeds.indexOf(Number(view));
    const rows = DraftResults.summary.rows.map(r => ({label:r.subset,value:view === 'median'?r.median:r.widths[index]}));
    rows.push({label:t('共享参考','Shared reference'),value:DraftResults.summary.inclusive_width});
    $('#width-output').innerHTML = `<p class="small">${view === 'median' ? t('当前显示：三种子中位数','Current view: three-seed median') : t(`当前显示：种子 ${view}`,`Current view: seed ${view}`)}</p><div class="width-axis"><span>W₆₈ = 0</span><span>1.8</span></div><div class="width-bars">${rows.map((r,i)=>`<div class="width-row${i===5?' reference':''}"><span>${r.label}</span><div class="bar-track"><div style="width:${100*r.value/1.8}%"></div></div><strong>${number(r.value)}</strong></div>`).join('')}</div><p class="small">${t('条长为名义宽度；没有添加差值误差条或种子置信区间。','Bar lengths are nominal widths, without contrast error bars or seed confidence intervals.')}</p>`;
  }
  $('#width-seed').addEventListener('change',showWidths);
  showWidths();

  let current = 1;
  const clamp = value => Math.max(1, Math.min(count, Number.isFinite(value)?Math.round(value):1));
  const fromHash = () => {
    const match = location.hash.match(/^#slide-(\d+)$/);
    const namedAnchors = {'#differences':25,'#widths':23,'#contrasts':25,'#spectra':17,'#provenance':30};
    return match ? clamp(Number(match[1])) : namedAnchors[location.hash] || current;
  };
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
