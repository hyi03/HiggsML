/* Event handlers only affect local teaching controls and aggregate displays. */
globalThis.Widgets = (() => {
  const H=H4L,{fmt,signed}=H;
  const options=(values,current,labels)=>values.map(v=>`<option value="${v}"${String(v)===String(current)?' selected':''}>${labels?labels(v):v}</option>`).join('');
  const seedSelect=(name='seed')=>`<label>种子 <select name="${name}" aria-label="训练种子">${options(H.D.seeds,42)}</select></label>`;
  const tbl=(heads,rows,caption='')=>`<div class="table-wrap"><table class="data-table">${caption?`<caption>${caption}</caption>`:''}<thead><tr>${heads.map(h=>`<th scope="col">${h}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr${['AC','BC','ABCD'].includes(r[0])?' class="highlight"':''}>${r.map((v,i)=>i?`<td>${v}</td>`:`<th scope="row">${v}</th>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  function network(el){
    const selected=new Set(['B','C']);
    el.innerHTML=`<div class="widget-controls" aria-label="选择网络输入">${[...'ABCD'].map(g=>`<button class="group-toggle" data-group="${g}" aria-pressed="${selected.has(g)}">组 ${g}</button>`).join('')}<button data-empty>空集基线</button></div><div class="widget-output"></div>`;
    const features={A:['lep1–4_pt','lep1–4_eta'],B:['mZ1','mZ2','deltaR_Z1','deltaR_Z2'],C:['pt4l','deltaPhi_ZZ'],D:['cos_theta_star','cos_theta_1','cos_theta_2','phi_decay_planes','phi_production_plane']};
    const update=()=>{const s=H.canon([...selected].join(''));el.querySelectorAll('[data-group]').forEach(b=>b.setAttribute('aria-pressed',selected.has(b.dataset.group)));el.querySelector('.widget-output').innerHTML=V.network(s)+`<p class="small">${s?[...s].map(g=>`<strong style="color:${V.colors[g]}">${g}</strong>：${features[g].join('、')}`).join('　'):'∅ 没有输入、标准化或训练步骤。所有事件进入一个有效计数类别。'}</p>`;};
    el.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;if(b.hasAttribute('data-empty'))selected.clear();else if(b.dataset.group)selected.has(b.dataset.group)?selected.delete(b.dataset.group):selected.add(b.dataset.group);update();});update();
  }
  function likelihood(el){
    el.innerHTML=`<div class="widget-controls"><label>示例 μ <input name="mu" type="range" min="0" max="4" step=".01" value="1" aria-label="教学信号强度 μ"></label><output class="mu-value">1.00</output><label>计数方式 <select name="split"><option value="yes">保留两个类别</option><option value="no">合并成一个计数</option></select></label><span>手工 T0 算例 · 不是论文 T1 拟合</span></div><div class="widget-output"></div>`;
    const update=()=>{const mu=+el.querySelector('[name="mu"]').value,split=el.querySelector('[name="split"]').value==='yes';el.querySelector('.mu-value').textContent=mu.toFixed(2);let out='';const x=v=>65+v/4*575,y=v=>280-Math.min(v,10)/10*240;
      for(let i=0;i<=4;i++)out+=V.line(x(i),40,x(i),280,'grid')+V.text(x(i),305,i,'tiny');for(let i=0;i<=10;i+=2)out+=V.line(65,y(i),640,y(i),'grid')+V.text(52,y(i)+4,i,'tiny','end');
      const critical=.9889464815,low=H.crossing(split,false),high=H.crossing(split,true);
      out+=`<rect x="${x(low)}" y="${y(critical)}" width="${x(high)-x(low)}" height="${280-y(critical)}" fill="#16836b22"/>`;
      out+=`<path d="${Array.from({length:201},(_,i)=>`${i?'L':'M'}${x(i/50)},${y(H.toyQ(i/50,split))}`).join(' ')}" fill="none" stroke="#126e89" stroke-width="3"/>`;
      out+=V.line(65,y(critical),640,y(critical),'axis','stroke-dasharray="5 4"')+V.text(640,y(critical)-7,'q = 0.98895','tiny','end');out+=V.circle(x(mu),y(H.toyQ(mu,split)),6,'#c66b16')+V.text(75,22,'q(μ)','label')+V.text(640,329,'μ','label');
      out+=V.line(x(low),335,x(high),335,'axis')+V.line(x(low),329,x(low),341,'axis')+V.line(x(high),329,x(high),341,'axis')+V.text((x(low)+x(high))/2,360,`W₆₈ = ${fmt(high,3)} − ${fmt(low,3)} = ${fmt(high-low,3)}`,'label');
      el.querySelector('.widget-output').innerHTML=`<div class="two wide"><div>${V.svg(out,'教学 T0 剖面似然曲线，阴影表示名义 68% 区间，橙点为所选 mu；下方标注宽度等于上端减下端',700,380)}</div><div><h3>固定 Asimov 观测</h3><p>${split?'s=(1,3)，b=(3,1)<br>n=(4,4)':'s=4，b=4<br>n=8'}</p><p>当前 λ = ${split?`(${fmt(mu+3,2)}, ${fmt(3*mu+1,2)})`:fmt(4*mu+4,2)}</p><p>q(μ) = ${fmt(H.toyQ(mu,split),3)}</p><div class="result-line">区间 [${fmt(low,3)}, ${fmt(high,3)}]<br>W₆₈ = ${fmt(high-low,3)}</div><p class="small">拖动 μ 只改变曲线上的探查点。固定观测的区间不会跟着移动。</p></div></div>`;
    };el.addEventListener('input',update);el.addEventListener('change',update);update();
  }
  function ranking(el){
    el.innerHTML=`<div class="widget-controls"><label>查看 <select name="seed">${options(['median',...H.D.seeds],'median',v=>v==='median'?'五种子中位数（主排名）':`种子 ${v}`)}</select></label><label>排序指标 <select name="metric"><option value="width68">W₆₈ 升序</option><option value="auc">AUC 降序</option></select></label><span>完整表保留所有 W₆₈；AUC 基线未记录。</span></div><div class="widget-output"></div>`;
    const update=()=>{const k=el.querySelector('[name="seed"]').value,metric=el.querySelector('[name="metric"]').value;const order=H.rank(k,metric);const rows=order.map((r,i)=>[`${i+1}. ${r.subset}`,...H.D.seeds.map(seed=>fmt(H.width(r.subset,seed))),fmt(H.median(H.D.seeds.map(seed=>H.width(r.subset,seed)))),fmt(H.median(H.D.seeds.map(seed=>H.record(r.subset,seed).auc))),fmt(r.value)]);rows.push(['∅ 基线',...H.D.seeds.map(seed=>fmt(H.width('',seed))),fmt(H.width('',42)),'—',metric==='width68'?fmt(H.width('',42)):'—']);
      el.querySelector('.widget-output').innerHTML=tbl(['组合',...H.D.seeds,'中位 W₆₈','中位 AUC',`当前${metric==='auc'?' AUC':' W₆₈'}`],rows)+`<div class="result-line">当前第一：<strong>${order[0].subset}</strong> · ${metric==='auc'?'AUC 最大':'W₆₈ 最小'}。五种子主排名：BC、AC、ABC、BCD、ABCD…</div>`;
    };el.addEventListener('change',update);update();
  }
  function pairwise(el){
    el.innerHTML=`<div class="widget-controls"><label>比较 S <select name="left">${options(H.D.subsets,'BC',H.label)}</select></label><label>参照 T <select name="right">${options(H.D.subsets,'ABCD',H.label)}</select></label><span>R = 1 − W(S,k) / W(T,k)</span></div><div class="widget-output"></div>`;
    const update=()=>{const s=el.querySelector('[name="left"]').value,t=el.querySelector('[name="right"]').value;const vals=H.D.seeds.map(k=>H.reduction(s,t,k)),correct=H.median(vals),shortcut=1-H.median(H.D.seeds.map(k=>H.width(s,k)))/H.median(H.D.seeds.map(k=>H.width(t,k)));
      el.querySelector('.widget-output').innerHTML=tbl(['种子','W(S)','W(T)','W(S) − W(T)','改善率 R'],H.D.seeds.map((k,i)=>[k,fmt(H.width(s,k)),fmt(H.width(t,k)),signed(H.width(s,k)-H.width(t,k)),signed(vals[i]*100,3)+'%']))+`<div class="two" style="margin-top:1cqw"><div class="result-line">先配对，后取中位数<br><strong>median(Rk) = ${signed(correct*100,3)}%</strong></div><div class="callout caution">如果误用两个宽度中位数的比值：${signed(shortcut*100,3)}%<br><span class="small">一般不相等；不要用它替换配对估计量。</span></div></div>`;
    };el.addEventListener('change',update);update();
  }
  function shapley(el){
    el.innerHTML=`<div class="widget-controls"><label>特征组 <select name="group">${options([...'ABCD'],'B')}</select></label>${seedSelect()}<label>加入顺序 <select name="order">${options(H.orders.map(a=>a.join('')),'ABCD',s=>[...s].join(' → '))}</select></label></div><div class="widget-output"></div>`;
    const update=()=>{const g=el.querySelector('[name="group"]').value,k=+el.querySelector('[name="seed"]').value,order=el.querySelector('[name="order"]').value;const others='ABCD'.replace(g,'');const rows=H.subsets(others).sort((a,b)=>a.length-b.length||a.localeCompare(b)).map(s=>[s||'∅',fmt(H.width(s,k)),fmt(H.width(s+g,k)),['1/4','1/12','1/12','1/4'][s.length],signed(H.gain(s,g,k)),signed(H.gain(s,g,k)*H.weights[s.length],6)]);let before='';const path=[...order].map(v=>{const inc=H.gain(before,v,k);const result=[`${before||'∅'} → ${H.canon(before+v)}`,signed(inc),v===g?'← 所选组':''];before=H.canon(before+v);return result;});const sum=[...'ABCD'].reduce((acc,v)=>acc+H.shapley(v,k),0);
      el.querySelector('.widget-output').innerHTML=`<div class="two wide"><div>${tbl(['S','W(S)','W(S∪G)','权重','边际贡献','加权贡献'],rows)}</div><div><h3>一个顺序的四步</h3>${tbl(['加入','贡献',''],path)}<p class="small">对 24 种顺序取平均，等于左侧八项加权求和。</p></div></div><div class="result-line">φ${g},${k} = <strong>${signed(H.shapley(g,k),6)}</strong>　Σφ = ${fmt(sum,6)} = W(∅) − W(ABCD)</div>`;
    };el.addEventListener('change',update);update();
  }
  function interaction(el){
    el.innerHTML=`<div class="widget-controls"><label>组对 GH <select name="pair">${options(['AB','AC','AD','BC','BD','CD'],'AC')}</select></label><label>已有组合 S <select name="conditioning"></select></label>${seedSelect()}<span>I = v(SGH) − v(SG) − v(SH) + v(S)</span></div><div class="widget-output"></div>`;
    const rebuild=()=>{const pair=el.querySelector('[name="pair"]').value;el.querySelector('[name="conditioning"]').innerHTML=options(H.subsets([...'ABCD'].filter(g=>!pair.includes(g)).join('')),'',s=>s||'∅');};
    const update=()=>{const p=el.querySelector('[name="pair"]').value,s=el.querySelector('[name="conditioning"]').value,k=+el.querySelector('[name="seed"]').value;const sets=[s+p,s+p[0],s+p[1],s].map(H.canon),signs=['+','−','−','+'];const val=H.interaction(p,s,k),med=H.median(H.D.seeds.map(seed=>H.interaction(p,s,seed)));
      el.querySelector('.widget-output').innerHTML=`<div class="two"><div class="four-grid">${sets.map((t,i)=>`<div><span>${signs[i]} v(${t||'∅'})</span><strong>${signed(-H.width(t,k))}</strong><span class="small">W = ${fmt(H.width(t,k))}</span></div>`).join('')}</div><div><h3>当前 I${p}|${s||'∅'} = ${signed(val)}</h3><p>${val>0?'此条件下，联合收益超过各自收益之和。':'此条件下，联合收益小于各自收益之和。'}</p><div class="result-line">五种子交互中位数：${signed(med)}</div><p class="small">更换 S 可能改变符号。先逐种子计算四项差，再取中位数。</p></div></div>`;
    };el.addEventListener('change',e=>{if(e.target.name==='pair')rebuild();update();});rebuild();update();
  }
  const registry={network,likelihood,ranking,pairwise,shapley,interaction};
  return {mount:()=>document.querySelectorAll('[data-widget]').forEach(el=>registry[el.dataset.widget](el))};
})();
